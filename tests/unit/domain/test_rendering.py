from __future__ import annotations

from datetime import date

from wellscope.domain.documents import (
    DocumentType,
    FieldValue,
    NextDayOperations,
    Operation,
    ParserInfo,
    QualityCheck,
    ReportDocument,
    ReportInfo,
    SourceInfo,
    Table,
    TimedNote,
    WellInfo,
)
from wellscope.domain.glossary import GlossaryEntry, GlossaryStatus
from wellscope.domain.rendering import (
    document_label,
    document_passages,
    glossary_passage,
    passage_text,
    render_document,
)

SOURCE = SourceInfo(
    file_name="r.pdf",
    relative_path="r.pdf",
    sha256="0" * 64,
    page_count=2,
    parser=ParserInfo(name="t", version="1"),
)


def make_document() -> ReportDocument:
    return ReportDocument(
        doc_id="ddr-well-a-1-0012",
        doc_type=DocumentType.DDR,
        title="Daily Operation Report",
        source=SOURCE,
        well=WellInfo(name="WELL-A-1"),
        report=ReportInfo(number=12, date=date(2026, 1, 14)),
        fields={
            "daily_cost": FieldValue(
                label="Daily Cost", section="costs", raw="250,000.00", value=250000.0, page=1
            ),
            "spud_date": FieldValue(
                label="Spud date",
                section="well_info",
                raw="02/01/2026",
                date=date(2026, 1, 2),
                page=1,
            ),
            "end_date": FieldValue(label="End date", section="well_info", raw="", page=1),
        },
        operations=[
            Operation(
                seq=1,
                date=date(2026, 1, 14),
                start="16:15",
                end="19:00",
                hours=2.75,
                phase_code="D18",
                activity_code="DRL",
                productive_code="OPRN",
                npt=True,
                rig_status="OPRN",
                md_from_m=1500.0,
                description="Attempt to open reamer.",
                page=2,
            )
        ],
        next_day=NextDayOperations(
            date=date(2026, 1, 15),
            entries=[
                TimedNote(start="00:00", end="02:00", description="Pull out of hole.", page=2)
            ],
        ),
        tables=[
            Table(
                section="lot_fit", page=2, header_rows=1, rows=[["EMW", "MAASP"], ["15.0", "2,000"]]
            )
        ],
        quality=[
            QualityCheck(id="dates.x", ok=False, severity="warning", detail="spud date is odd"),
            QualityCheck(id="ok.check", ok=True, severity="warning", detail="fine"),
        ],
    )


def passages_by_kind(document: ReportDocument) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for passage in document_passages(document):
        grouped.setdefault(passage.kind, []).append(passage.body)
    return grouped


def test_document_label_names_type_number_and_date() -> None:
    assert document_label(make_document()) == "DDR #12 (2026-01-14)"


def test_field_passages_group_by_section_and_show_blank_and_iso_dates() -> None:
    facts = "\n".join(passages_by_kind(make_document())["facts"])
    assert "- Daily Cost: 250,000.00" in facts
    assert "- Spud date: 02/01/2026 (2026-01-02)" in facts
    assert "- End date: (blank)" in facts


def test_operation_passage_spells_out_codes_and_npt() -> None:
    body = passages_by_kind(make_document())["operation"][0]
    assert "2026-01-14 16:15–19:00 (2.75 h)" in body
    assert "NPT: yes" in body
    assert "Attempt to open reamer." in body


def test_next_day_table_and_quality_passages() -> None:
    kinds = passages_by_kind(make_document())
    assert "Pull out of hole." in kinds["next_day"][0]
    assert kinds["table"][0].splitlines() == [
        "| EMW | MAASP |",
        "| --- | --- |",
        "| 15.0 | 2,000 |",
    ]
    assert kinds["quality"] == ["- spud date is odd (warning)"]


def test_passage_text_prefixes_provenance() -> None:
    document = make_document()
    operation = next(p for p in document_passages(document) if p.kind == "operation")
    header = passage_text(document, operation).splitlines()[0]
    assert header == "[DDR #12 (2026-01-14) · WELL-A-1 · Operation 16:15–19:00 · p.2]"


def test_render_document_contains_every_passage_title() -> None:
    rendered = render_document(make_document())
    assert rendered.startswith("# DDR #12 (2026-01-14) · WELL-A-1")
    assert "## Operation 16:15–19:00 (p.2)" in rendered
    assert "## Data-quality notes" in rendered


def test_glossary_passage_states_status_aliases_and_senses() -> None:
    entry = GlossaryEntry(
        id="gl-zz",
        term="ZZ",
        aliases=("ZZ", "Zz"),
        expansion="Zone Zero / Zig Zag",
        description="Two meanings.",
        status=GlossaryStatus.TO_BE_CONFIRMED,
        senses=("Zone Zero", "Zig Zag"),
        source_row=3,
    )
    body = glossary_passage(entry).body
    assert body.startswith("ZZ — Zone Zero / Zig Zag: Two meanings.")
    assert "to be confirmed" in body
    assert "Also written: Zz" in body
    assert "Meanings: 1) Zone Zero 2) Zig Zag" in body


def test_glossary_passage_for_unknown_terms_says_so() -> None:
    entry = GlossaryEntry(
        id="gl-qq",
        term="QQ",
        aliases=("QQ",),
        description="Seen in a field.",
        status=GlossaryStatus.UNKNOWN,
        source_row=1,
    )
    assert glossary_passage(entry).body == (
        "QQ — meaning unknown: Seen in a field. (The glossary marks this term as unknown.)"
    )
