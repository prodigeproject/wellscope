from __future__ import annotations

import pytest

from wellscope.domain.messages import Language, MessageKind, message, not_found


@pytest.mark.parametrize("kind", list(MessageKind))
@pytest.mark.parametrize("language", list(Language))
def test_every_message_exists_in_both_languages(kind: MessageKind, language: Language) -> None:
    assert message(kind, language).strip()


def test_out_of_scope_redirects_to_supported_topics() -> None:
    english = message(MessageKind.OUT_OF_SCOPE, Language.EN)
    indonesian = message(MessageKind.OUT_OF_SCOPE, Language.ID)
    assert english.startswith("Sorry, that question is outside the scope of my data.")
    assert indonesian.startswith("Maaf, pertanyaan tersebut berada di luar cakupan data")
    for text in (english, indonesian):
        assert "DDR" in text
        assert "DGOS" in text
        assert "NPT" in text


def test_not_found_lists_the_available_reports() -> None:
    text = not_found(Language.EN, ["DDR #32 (2026-07-19)", "DGOS #72 (2026-08-29)"])
    assert text.startswith("I couldn't find that information in the available documents.")
    assert text.endswith("Available reports: DDR #32 (2026-07-19), DGOS #72 (2026-08-29).")
    assert not_found(Language.ID, []) == message(MessageKind.NOT_FOUND, Language.ID)
