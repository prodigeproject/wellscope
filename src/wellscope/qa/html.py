"""Answer markdown to sanitised HTML; citations become buttons that open their source.

Raw HTML in the markdown is never rendered, links and images are removed (an answer must not
point anywhere a document told it to), and the result passes an allow-list sanitiser.
"""

from __future__ import annotations

import re
from collections.abc import Collection

import nh3
from markdown_it import MarkdownIt

ALLOWED_TAGS = {
    "p", "br", "strong", "em", "del", "code", "pre", "blockquote", "hr",
    "ul", "ol", "li", "h3", "h4", "table", "thead", "tbody", "tr", "th", "td",
}  # fmt: skip
_MARKDOWN = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable("table")
_CITATION = re.compile(r"\[\s*(S\d{1,3}(?:\s*[,;]\s*S\d{1,3})*)\s*\]")
_BUTTON = '<button type="button" class="cite" data-source="{id}">{id}</button>'


def render_answer(markdown: str, source_ids: Collection[str]) -> str:
    """Safe HTML for ``markdown``; citations of unknown sources are dropped."""
    rendered = _MARKDOWN.render(markdown)
    clean = nh3.clean(rendered, tags=ALLOWED_TAGS, attributes={}, url_schemes=set())
    return _CITATION.sub(lambda match: _buttons(match.group(1), source_ids), clean)


def _buttons(ids: str, source_ids: Collection[str]) -> str:
    wanted = [source_id.strip() for source_id in re.split(r"[,;]", ids)]
    return "".join(_BUTTON.format(id=source_id) for source_id in wanted if source_id in source_ids)
