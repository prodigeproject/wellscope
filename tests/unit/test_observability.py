from __future__ import annotations

import json
import logging

from wellscope.observability import REDACTED, JsonFormatter, redact, request_id_var


def test_redact_masks_api_keys_and_bearer_tokens() -> None:
    key = "sk-" + "c" * 40
    text = f"key={key} header=Bearer abcdefghijklmnop"
    masked = redact(text)
    assert key not in masked
    assert "abcdefghijklmnop" not in masked
    assert masked.count(REDACTED) == 2
    assert "Bearer " in masked


def test_redact_leaves_ordinary_text_untouched() -> None:
    assert redact("Daily cost 1,200.00 USD") == "Daily cost 1,200.00 USD"


def test_json_formatter_includes_request_id_extras_and_redacts() -> None:
    key = "sk-" + "d" * 40
    record = logging.LogRecord(
        "wellscope.test", logging.INFO, __file__, 1, "using %s", (key,), None
    )
    record.stage = "answer"
    token = request_id_var.set("req-123")
    try:
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert payload["request_id"] == "req-123"
    assert payload["stage"] == "answer"
    assert key not in payload["message"]
