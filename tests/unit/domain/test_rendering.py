from __future__ import annotations

from tests.support.documents import make_document
from wellscope.domain.documents import FieldValue, ReportDocument, Table
from wellscope.domain.glossary import GlossaryEntry, GlossaryStatus
from wellscope.domain.rendering import (
    catalog_summary,
    document_label,
    document_passages,
    glossary_passage,
    passage_text,
    render_document,
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


def test_catalog_summary_lists_key_facts_that_are_present() -> None:
    assert catalog_summary(make_document()) == "Daily Cost: 250,000.00"


def test_operation_totals_follow_the_operations() -> None:
    kinds = [passage.kind for passage in document_passages(make_document())]
    assert kinds.index("totals") == kinds.index("operation") + 1
    totals = passages_by_kind(make_document())["totals"][0]
    assert "- NPT: 2.75 h (16:15–19:00)" in totals


def test_tables_with_flattened_columns_render_them_as_the_header() -> None:
    table = Table(
        section="casing",
        page=1,
        header_rows=1,
        columns=["HOLE", "SHOE m"],
        rows=[["HOLE", "SHOE"], ["17-1/2", "1500.50"]],
    )
    document = make_document().model_copy(update={"tables": [table]})
    body = passages_by_kind(document)["table"][0]
    assert body.splitlines() == ["| HOLE | SHOE m |", "| --- | --- |", "| 17-1/2 | 1500.50 |"]


def test_glossary_passage_without_expansion_gives_the_description() -> None:
    entry = GlossaryEntry(
        id="gl-bb", term="BB", aliases=("BB",), description="Field name.", source_row=2
    )
    assert glossary_passage(entry).body == "BB: Field name."


def _with_mud_and_safety(document: ReportDocument) -> ReportDocument:
    fields = {
        **document.fields,
        "drill_type": FieldValue(label="Drill type", section="safety", raw="Man Overboard", page=3),
        "mud_weight": FieldValue(label="MW ppg", section="progress", raw="9.9 SBM", page=1),
    }
    mud = Table(
        section="mud_check", page=2, rows=[["Type", "SBM", ""], ["Density (ppg)", "9.80", ""]]
    )
    return document.model_copy(update={"fields": fields, "tables": [mud]})


def test_abbreviated_labels_carry_their_everyday_name() -> None:
    grouped = passages_by_kind(_with_mud_and_safety(make_document()))
    facts = "\n".join(grouped["facts"])
    assert "- Drill type (safety drill conducted): Man Overboard" in facts
    assert "- MW ppg (mud weight): 9.9 SBM" in facts
    assert "| Density (ppg) (mud weight) | 9.80 |   |" in grouped["table"][0]


def test_catalog_summary_takes_the_mud_weight_from_the_mud_check_table() -> None:
    document = _with_mud_and_safety(make_document())
    document = document.model_copy(
        update={"fields": {k: v for k, v in document.fields.items() if k != "mud_weight"}}
    )
    assert catalog_summary(document) == "Daily Cost: 250,000.00; Mud weight (density, ppg): 9.80"
