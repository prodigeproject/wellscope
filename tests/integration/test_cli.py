"""The CLI end to end, offline: no API key, so no model is ever called."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from wellscope.cli import app
from wellscope.config import get_settings
from wellscope.domain.schemas import json_schemas

EXAMPLE_GOLDEN = Path(__file__).resolve().parents[2] / "evals" / "golden.example.yaml"
runner = CliRunner()


@pytest.fixture
def offline(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Settings pointing at the synthetic data folder, with no API key."""
    output = data_dir.parent / "processed"
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("WELLSCOPE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("WELLSCOPE_OUTPUT_DIR", str(output))
    get_settings.cache_clear()
    yield output
    get_settings.cache_clear()


def test_ingest_builds_outputs_and_a_keyword_index(offline: Path) -> None:
    result = runner.invoke(app, ["ingest"])
    assert result.exit_code == 0, result.output
    assert "keyword only" in result.output
    assert (offline / "manifest.json").is_file()
    assert (offline / "wellscope.db").is_file()


def test_ask_reports_a_missing_key_as_json(offline: Path) -> None:
    assert runner.invoke(app, ["ingest"]).exit_code == 0
    result = runner.invoke(app, ["ask", "What is the oil rate?", "--json"])
    assert result.exit_code == 0, result.output
    answer = json.loads(result.output)
    assert answer["status"] == "error"
    assert answer["reason"] == "no_api_key"


def test_schema_writes_one_file_per_output(tmp_path: Path) -> None:
    result = runner.invoke(app, ["schema", "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    for name, schema in json_schemas().items():
        written = json.loads((tmp_path / f"{name}.schema.json").read_text(encoding="utf-8"))
        assert written == schema


def test_eval_runs_a_golden_set_and_writes_reports(
    offline: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    reports = tmp_path / "reports"
    result = runner.invoke(app, ["eval", "--set", str(EXAMPLE_GOLDEN), "--reports", str(reports)])
    assert result.exit_code == 0, result.output
    assert "Accuracy" in result.output
    assert list(reports.glob("eval-*.md"))
    assert list((tmp_path / "evals" / "private" / "runs").glob("eval-*.jsonl"))


def test_ingest_reports_a_missing_data_folder_and_exits_with_an_error(
    offline: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WELLSCOPE_DATA_DIR", str(offline.parent / "does-not-exist"))
    get_settings.cache_clear()
    result = runner.invoke(app, ["ingest"])
    assert result.exit_code == 1
    assert "does not exist" in result.output


def test_serve_ignores_forwarded_client_addresses(
    offline: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Trusting X-Forwarded-For from a local client would let any caller pick its own
    # rate-limit key.
    import uvicorn  # noqa: PLC0415 - patched only for this test

    calls: list[dict[str, object]] = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **options: calls.append(options))
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 0, result.output
    assert calls[0]["proxy_headers"] is False
    assert calls[0]["host"] == "127.0.0.1"
