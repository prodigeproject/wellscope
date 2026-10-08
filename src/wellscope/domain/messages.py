"""Canonical user-facing messages in Indonesian and English; tests lock their wording."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum


class Language(StrEnum):
    """Language of a question and of its answer."""

    ID = "id"
    EN = "en"


class MessageKind(StrEnum):
    """Situations answered with a fixed message instead of a generated one."""

    OUT_OF_SCOPE = "out_of_scope"
    NOT_FOUND = "not_found"
    NO_INDEX = "no_index"
    NO_API_KEY = "no_api_key"
    MODEL_ERROR = "model_error"


_MESSAGES: dict[MessageKind, dict[Language, str]] = {
    MessageKind.OUT_OF_SCOPE: {
        Language.ID: (
            "Maaf, pertanyaan tersebut berada di luar cakupan data yang saya miliki. Saya hanya "
            "menjawab berdasarkan laporan harian sumur (Daily Drilling Report/DDR dan Daily "
            "Geological Operations Summary/DGOS) serta glosarium istilah Oil & Gas. Silakan "
            "tanyakan, misalnya: status operasi, kedalaman, biaya, lumpur pemboran, BHA, "
            "formation tops, keselamatan & personel, atau arti istilah seperti NPT dan BHA."
        ),
        Language.EN: (
            "Sorry, that question is outside the scope of my data. I only answer from the daily "
            "well reports (Daily Drilling Report/DDR and Daily Geological Operations "
            "Summary/DGOS) and the Oil & Gas glossary. Try asking about operations status, "
            "depths, costs, drilling fluids, BHA, formation tops, safety & personnel, or what a "
            "term such as NPT or BHA means."
        ),
    },
    MessageKind.NOT_FOUND: {
        Language.ID: (
            "Informasi tersebut tidak ditemukan dalam dokumen yang tersedia. Saya hanya menjawab "
            "berdasarkan laporan sumur (DDR/DGOS) dan glosarium yang sudah di-ingest."
        ),
        Language.EN: (
            "I couldn't find that information in the available documents. I only answer from "
            "the ingested well reports (DDR/DGOS) and the glossary."
        ),
    },
    MessageKind.NO_INDEX: {
        Language.ID: "Belum ada data. Jalankan `wellscope ingest` terlebih dahulu.",
        Language.EN: "No data yet. Run `wellscope ingest` first.",
    },
    MessageKind.NO_API_KEY: {
        Language.ID: (
            "API key belum dikonfigurasi. Isi OPENAI_API_KEY di file .env, lalu jalankan "
            "`wellscope doctor`."
        ),
        Language.EN: (
            "The API key is not configured. Set OPENAI_API_KEY in the .env file, then run "
            "`wellscope doctor`."
        ),
    },
    MessageKind.MODEL_ERROR: {
        Language.ID: "Layanan model sedang bermasalah. Silakan coba lagi sebentar lagi.",
        Language.EN: "The model service is having trouble. Please try again shortly.",
    },
}
_AVAILABLE_REPORTS = {
    Language.ID: "Laporan tersedia: {reports}.",
    Language.EN: "Available reports: {reports}.",
}


def message(kind: MessageKind, language: Language) -> str:
    """The canonical text for ``kind``."""
    return _MESSAGES[kind][language]


def not_found(language: Language, reports: Sequence[str]) -> str:
    """The not-found message, followed by the reports that do exist."""
    text = message(MessageKind.NOT_FOUND, language)
    if not reports:
        return text
    return f"{text} {_AVAILABLE_REPORTS[language].format(reports=', '.join(reports))}"
