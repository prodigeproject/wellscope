from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.support.documents import make_document
from tests.support.index import build_test_index
from tests.support.web import make_client, make_settings
from wellscope.storage.index_reader import SearchIndex

QUESTION = {"question": "What was the daily cost in DDR 12?"}


def events(body: str) -> list[tuple[str, dict[str, Any]]]:
    parsed = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if not line.startswith(":"))
        if lines:
            parsed.append((lines["event"], json.loads(lines["data"])))
    return parsed


def test_health_reports_the_index_and_model_state(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["documents"] == 1
    assert body["glossary_entries"] == 1
    assert body["model_configured"] is True
    assert body["index_version"] == "v1"


def test_health_without_an_index_asks_for_ingest(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    with make_client(settings, SearchIndex(settings.database_path)) as client:
        body = client.get("/api/health").json()
    assert body["status"] == "no_index"
    assert body["documents"] == 0


def test_every_response_carries_security_headers_and_a_request_id(client: TestClient) -> None:
    for path in ("/", "/api/health", "/api/sources/nope"):
        response = client.get(path)
        csp = response.headers["content-security-policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "'unsafe-inline'" not in csp
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert len(response.headers["x-request-id"]) == 32


def test_api_responses_are_not_cached(client: TestClient) -> None:
    assert client.get("/api/catalog").headers["cache-control"] == "no-store"


def test_catalog_lists_reports_and_suggests_questions(client: TestClient) -> None:
    body = client.get("/api/catalog").json()
    document = body["documents"][0]
    assert document["label"] == "DDR #12 (2026-01-14)"
    assert document["doc_type"] == "DDR"
    assert body["glossary_entries"] == 1
    assert any("DDR 12" in question for question in body["suggestions"])


def test_glossary_search(client: TestClient) -> None:
    assert client.get("/api/glossary").json()["entries"][0]["term"] == "NPT"
    assert client.get("/api/glossary", params={"q": "productive"}).json()["entries"]
    assert client.get("/api/glossary", params={"q": "weather"}).json()["entries"] == []


def test_sources_accept_only_report_ids(client: TestClient) -> None:
    report = client.get("/api/sources/ddr-well-a-1-0012").json()
    assert report["label"] == "DDR #12 (2026-01-14)"
    assert "Daily Cost" in report["html"]
    assert client.get("/api/sources/unknown-report").status_code == 404
    invalid = client.get("/api/sources/..%2F..%2Fsecrets")
    assert invalid.status_code in (404, 422)


def test_chat_streams_stages_then_a_cited_answer(client: TestClient) -> None:
    response = client.post("/api/chat", json=QUESTION)
    assert response.headers["content-type"].startswith("text/event-stream")
    stream = events(response.text)
    stages = [data["stage"] for name, data in stream if name == "stage"]
    assert stages == ["analyzing", "retrieving", "composing", "verifying"]
    name, answer = stream[-1]
    assert name == "answer"
    assert answer["status"] == "answered"
    assert answer["verified"] is True
    assert "<strong>250,000.00</strong>" in answer["html"]
    assert answer["citations"][0]["label"] == "DDR #12 (2026-01-14)"
    assert answer["meta"]["request_id"] == response.headers["x-request-id"]
    assert answer["meta"]["cost_usd"] is None  # fake models have no list price


def test_chat_validates_the_request(client: TestClient) -> None:
    for payload in (
        {"question": ""},
        {"question": "x" * 1001},
        {"question": "ok", "extra": 1},
        {"question": "ok", "history": [{"question": "q", "answer": "a"}] * 4},
    ):
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "invalid_request"
        assert error["request_id"] == response.headers["x-request-id"]


def test_oversized_bodies_are_rejected_before_parsing(client: TestClient) -> None:
    response = client.post("/api/chat", content=b"{" + b" " * 20_000 + b"}")
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_chat_is_rate_limited_per_client(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, rate_limit_per_min=2)
    with make_client(settings, SearchIndex(settings.database_path)) as limited:
        statuses = [limited.post("/api/chat", json=QUESTION).status_code for _ in range(4)]
        response = limited.post("/api/chat", json=QUESTION)
    assert statuses[:2] == [200, 200]
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) >= 1
    assert response.json()["error"]["code"] == "rate_limited"


def test_unknown_hosts_are_refused(client: TestClient) -> None:
    response = client.get("/api/health", headers={"host": "attacker.example"})
    assert response.status_code == 400


def test_the_web_app_is_served_without_inline_scripts(client: TestClient) -> None:
    page = client.get("/")
    assert page.status_code == 200
    assert '<script type="module" src="/assets/js/app.js"></script>' in page.text
    assert "<script>" not in page.text
    assert " style=" not in page.text
    assert client.get("/assets/css/tokens.css").status_code == 200


def test_question_text_is_logged_only_when_enabled(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    for enabled in (False, True):
        settings = make_settings(tmp_path / str(enabled), log_questions=enabled)
        index = build_test_index(settings.database_path, [make_document()])
        caplog.clear()
        with make_client(settings, index) as client, caplog.at_level(logging.INFO):
            client.post("/api/chat", json=QUESTION)
        record = next(r for r in caplog.records if r.getMessage() == "question received")
        assert (getattr(record, "question", None) == QUESTION["question"]) is enabled
