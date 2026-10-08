"""Grounded answer generation: the model sees only numbered, escaped, nonce-delimited sources."""

from __future__ import annotations

import html
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from wellscope.domain.messages import Language
from wellscope.errors import ModelError
from wellscope.llm.ports import ChatModel, ChatRequest, ChatResult
from wellscope.qa.prompts import load_prompt
from wellscope.retrieval.context import format_sources
from wellscope.retrieval.models import Source

AnswerStatus = Literal["answered", "not_found", "out_of_scope"]
ANSWER_MAX_TOKENS = 1500
NONCE_BYTES = 12
LANGUAGE_NAMES = {Language.ID: "Indonesian (Bahasa Indonesia)", Language.EN: "English"}


@dataclass(frozen=True, slots=True)
class Draft:
    """The model's answer before verification."""

    status: AnswerStatus
    markdown: str
    citations: tuple[str, ...]
    caveats: tuple[str, ...]


class _Reply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AnswerStatus
    answer_markdown: str
    citations: list[str]
    caveats: list[str]


_STRINGS = {"type": "array", "items": {"type": "string"}}
SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": list(_Reply.model_fields),
    "properties": {
        "status": {"type": "string", "enum": ["answered", "not_found", "out_of_scope"]},
        "answer_markdown": {"type": "string"},
        "citations": _STRINGS,
        "caveats": _STRINGS,
    },
}


class Answerer:
    """Asks the answer model for a cited answer drawn only from the given sources."""

    def __init__(self, model: ChatModel) -> None:
        self._model = model
        self._prompt = load_prompt("answer")

    def answer(
        self,
        question: str,
        language: Language,
        sources: Sequence[Source],
        feedback: str | None = None,
    ) -> tuple[Draft, ChatResult]:
        """Draft an answer; ``feedback`` explains why the previous draft failed verification."""
        nonce = secrets.token_hex(NONCE_BYTES)
        system = self._prompt.replace("{language}", LANGUAGE_NAMES[language]).replace(
            "{nonce}", nonce
        )
        parts = [
            f"<sources>\n{format_sources(sources, nonce)}\n</sources>",
            f"<question>{html.escape(question, quote=False)}</question>",
        ]
        if feedback:
            parts.append(
                f"Your previous answer failed verification: {feedback} Answer again, using only "
                "values that appear in the sources you cite."
            )
        request = ChatRequest(
            system=system,
            user="\n\n".join(parts),
            schema_name="grounded_answer",
            schema=SCHEMA,
            max_output_tokens=ANSWER_MAX_TOKENS,
        )
        result = self._model.complete(request)
        try:
            reply = _Reply.model_validate(result.content)
        except ValidationError as error:
            raise ModelError("answer did not match the schema", code="model_bad_output") from error
        draft = Draft(
            status=reply.status,
            markdown=reply.answer_markdown.strip(),
            citations=tuple(reply.citations),
            caveats=tuple(caveat.strip() for caveat in reply.caveats if caveat.strip()),
        )
        return draft, result
