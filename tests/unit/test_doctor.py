from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from wellscope.cli import app
from wellscope.config import Settings
from wellscope.doctor import model_checks, run_checks
from wellscope.errors import ModelError
from wellscope.llm.fakes import FakeChatModel, HashEmbedder


def make_settings(tmp_path: Path, **values: object) -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None, data_dir=tmp_path / "raw", output_dir=tmp_path / "out", **values
    )


def checks_by_id(settings: Settings) -> dict[str, tuple[bool, str]]:
    return {check.id: (check.ok, check.detail) for check in run_checks(settings)}


def test_doctor_reports_missing_key_without_printing_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    ok, _ = checks_by_id(make_settings(tmp_path))["api_key"]
    assert ok is False


def test_doctor_hides_configured_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "sk-" + "e" * 32
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    ok, detail = checks_by_id(make_settings(tmp_path))["api_key"]
    assert ok is True
    assert secret not in detail


def test_doctor_counts_source_documents(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "nested"
    raw.mkdir(parents=True)
    (raw / "report.pdf").write_bytes(b"%PDF-1.4")
    (raw / "notes.txt").write_text("ignored", encoding="utf-8")
    ok, detail = checks_by_id(make_settings(tmp_path))["data_dir"]
    assert ok is True
    assert detail.startswith("1 source files")


def test_doctor_flags_missing_index(tmp_path: Path) -> None:
    ok, detail = checks_by_id(make_settings(tmp_path))["index"]
    assert ok is False
    assert "wellscope ingest" in detail


def test_cli_version_flag_prints_version() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.startswith("wellscope ")


def test_model_checks_report_reachable_and_failing_models() -> None:
    def denied(request: object) -> dict[str, object]:
        raise ModelError("the configured model is not available", code="model_unavailable")

    checks = model_checks(
        {"chat": FakeChatModel(lambda request: {"ok": True}), "analyzer": FakeChatModel(denied)},
        HashEmbedder(),
    )
    by_id = {check.id: check for check in checks}
    assert by_id["model.chat"].ok
    assert not by_id["model.analyzer"].ok
    assert "model_unavailable" in by_id["model.analyzer"].detail
    assert by_id["model.embeddings"].ok
