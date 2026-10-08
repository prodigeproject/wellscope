"""Deterministic reading of a question: cleaning, language, and the reports it names.

Report numbers and dates found here override the analyzer's, because a model can misread a
number; the analyzer still decides scope and intent.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass

from wellscope.domain.dates import MONTHS, find_dates
from wellscope.domain.messages import Language

DOC_TYPES = {
    "DDR": re.compile(
        r"\bDDR\b|daily\s+drilling\s+report|laporan\s+(?:harian\s+)?pengeboran", re.IGNORECASE
    ),
    "DGOS": re.compile(
        r"\bDGOS\b|geological\s+(?:operations?\s+)?summary|laporan\s+geologi", re.IGNORECASE
    ),
}
_MONTH_NAMES = "|".join(sorted(MONTHS, key=len, reverse=True))
_NUMBER = r"\d{1,3}"
_JOINER = r"\s*(?:,|&|and|dan|or|atau|vs\.?|versus|with|dengan)\s*(?:(?:DDR|DGOS)\s*)?#?\s*"
_REPORT_REFERENCE = re.compile(
    r"\b(?:DDR|DGOS|reports?|laporan|rpt)\b\.?\s*"
    r"(?:(?:no|nr|number|nomor|nomer)\.?\s*|ke-?\s*|#\s*)?"
    rf"(?P<numbers>{_NUMBER}(?:{_JOINER}{_NUMBER})*)"
    # not the start of a date such as "19 Juli", "19/07" or "2026-07-19"
    rf"(?!\d|\s*[/.:-]\s*\d|\s+(?:{_MONTH_NAMES})\b)",
    re.IGNORECASE,
)
_LATEST = re.compile(
    r"\b(?:latest|most\s+recent|newest|terbaru|paling\s+baru|"
    r"(?:laporan|report)\s+terakhir|last\s+report)\b",
    re.IGNORECASE,
)
_INDONESIAN_WORDS = frozenset(
    """
    apa apakah berapa bagaimana kapan dimana mana siapa mengapa kenapa yang dan atau di ke
    dari pada untuk dengan adalah itu ini tersebut saja juga sudah telah akan bisa tolong
    mohon jelaskan sebutkan tentang dalam oleh laporan tanggal jam pukul hari sumur biaya
    kedalaman arti artinya kepanjangan singkatan halo hai terima kasih selamat bandingkan
    tampilkan berikan ada tidak saat ini kemarin
    """.split()  # noqa: SIM905 - a long word list reads better as text
)
_ENGLISH_WORDS = frozenset(
    """
    what which who whom when where why how is are was were the a an of in on at to for from
    by with and or does do did tell show give please explain list compare report reports
    hello hi thanks mean means stand
    """.split()  # noqa: SIM905 - a long word list reads better as text
)
_HORIZONTAL_SPACE = re.compile(r"[^\S\n]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_WORD = re.compile(r"[a-z]+")


@dataclass(frozen=True, slots=True)
class References:
    """Reports a question names explicitly."""

    doc_types: tuple[str, ...] = ()
    report_numbers: tuple[int, ...] = ()
    dates: tuple[dt.date, ...] = ()
    latest: bool = False

    @property
    def any(self) -> bool:
        """Whether the question names a report type, number or date."""
        return bool(self.doc_types or self.report_numbers or self.dates)


def clean_question(text: str) -> str:
    """NFKC-normalise, drop control and invisible characters, and tidy whitespace."""
    normalised = unicodedata.normalize("NFKC", text).replace("\t", " ")
    visible = "".join(
        char
        for char in normalised
        if char == "\n" or not unicodedata.category(char).startswith("C")
    )
    lines = (line.strip() for line in _HORIZONTAL_SPACE.sub(" ", visible).split("\n"))
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def detect_language(text: str) -> Language:
    """Indonesian when Indonesian function words outnumber English ones, else English."""
    words = _WORD.findall(text.casefold())
    indonesian = sum(word in _INDONESIAN_WORDS for word in words)
    english = sum(word in _ENGLISH_WORDS for word in words)
    return Language.ID if indonesian > english else Language.EN


def extract_references(question: str, default_year: int | None) -> References:
    """Report types, numbers and dates named in ``question``, in order of appearance."""
    positions = {
        doc_type: match.start()
        for doc_type, pattern in DOC_TYPES.items()
        if (match := pattern.search(question))
    }
    numbers = [
        int(number)
        for match in _REPORT_REFERENCE.finditer(question)
        for number in re.findall(_NUMBER, match["numbers"])
    ]
    return References(
        doc_types=tuple(sorted(positions, key=positions.__getitem__)),
        report_numbers=tuple(dict.fromkeys(numbers)),
        dates=tuple(dict.fromkeys(find_dates(question, default_year))),
        latest=bool(_LATEST.search(question)),
    )
