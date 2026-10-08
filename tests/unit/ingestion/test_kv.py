from __future__ import annotations

from wellscope.ingestion.pdf.kv import LabelSpec, TextLine, extract_pairs

DEPTH_LABELS = [
    LabelSpec("dol", ("DOL",)),
    LabelSpec("md", ("MD",)),
    LabelSpec("rotating_hrs", ("Rotating Hrs",)),
    LabelSpec("last_casing", ("Last Casing",)),
    LabelSpec("last_shoe_tmd", ("Last Shoe TMD",)),
    LabelSpec("daily_npt", ("Daily NPT",)),
]


def test_extract_pairs_splits_several_labels_on_one_line() -> None:
    lines = ["DOL : 29.04 days MD : 1,200.00 m Rotating Hrs : Last Casing : 20.000 in"]
    assert extract_pairs(lines, DEPTH_LABELS) == {
        "dol": "29.04 days",
        "md": "1,200.00 m",
        "rotating_hrs": "",
        "last_casing": "20.000 in",
    }


def test_extract_pairs_requires_a_label_boundary() -> None:
    # "MD :" inside "TMD :" must not be read as the MD label.
    pairs = extract_pairs(["Last Shoe TMD : 1,128.00 m"], DEPTH_LABELS)
    assert pairs == {"last_shoe_tmd": "1,128.00 m"}


def test_extract_pairs_reads_values_written_below_their_label() -> None:
    specs = [LabelSpec("objective", ("Objective",)), LabelSpec("afe", ("AFE No.",))]
    assert extract_pairs(["Objective:", "EXPLORATION"], specs) == {"objective": "EXPLORATION"}
    assert extract_pairs(["AFE No.:", "P.CP0.ABC"], specs) == {"afe": "P.CP0.ABC"}


def test_extract_pairs_appends_continuation_lines_to_the_previous_value() -> None:
    specs = [LabelSpec("summary", ("24 hr summary",)), LabelSpec("remarks", ("Remarks",))]
    lines = ["24 hr summary : Continue drilling", "to section TD.", "Remarks :"]
    assert extract_pairs(lines, specs) == {
        "summary": "Continue drilling to section TD.",
        "remarks": "",
    }


def test_extract_pairs_ignores_text_before_the_first_label() -> None:
    assert extract_pairs(["Noise text", "DOL : 1.00 days"], DEPTH_LABELS) == {"dol": "1.00 days"}


def test_extract_pairs_accepts_aliases_and_ignores_case() -> None:
    specs = [LabelSpec("engineer", ("PTT Engineer", "Company Engineer"))]
    assert extract_pairs(["company engineer: J. Doe"], specs) == {"engineer": "J. Doe"}


def test_extract_pairs_keeps_the_first_occurrence_of_a_repeated_label() -> None:
    specs = [LabelSpec("well", ("Well",))]
    assert extract_pairs(["Well: A-1", "Well: A-1 (repeat)"], specs) == {"well": "A-1"}


def test_extract_pairs_reads_heading_labels_that_stand_alone_on_a_line() -> None:
    headings = [
        LabelSpec("last_24h", ("LAST 24 HRS OPERATION",)),
        LabelSpec("next_24h", ("NEXT 24 HRS OPERATION",)),
    ]
    lines = [
        "LAST 24 HRS OPERATION",
        "Pulled out of hole.",
        "Rigged up wireline.",
        "NPT: 1.50 hrs due to weather.",
        "NEXT 24 HRS OPERATION",
        "Run in hole.",
    ]
    pairs = extract_pairs(lines, [LabelSpec("npt", ("NPT",))], headings=headings)
    assert pairs == {
        "last_24h": "Pulled out of hole. Rigged up wireline.",
        "npt": "1.50 hrs due to weather.",
        "next_24h": "Run in hole.",
    }


def test_extract_pairs_with_only_headings_never_matches_empty_labels() -> None:
    headings = [LabelSpec("objectives", ("OBJECTIVES",))]
    lines = ["OBJECTIVES", "Explore reservoir X: below field Y."]
    assert extract_pairs(lines, [], headings=headings) == {
        "objectives": "Explore reservoir X: below field Y."
    }


def test_extract_pairs_ignores_unaligned_text_after_a_value() -> None:
    # A centred title printed beside "AFE No." must not be read as part of its value.
    specs = [LabelSpec("afe", ("AFE No.",)), LabelSpec("date", ("Current Date",))]
    lines = [
        TextLine.from_words([("AFE", 16), ("No.", 30), (":", 61), ("P.CP0.ABC", 69)]),
        TextLine.from_words([("ACME", 315), ("ENERGY", 340)]),
        TextLine.from_words([("DAILY", 287), ("SUMMARY", 320)]),
        TextLine.from_words([("Current", 16), ("Date", 50), (":", 84), ("10-09-2026", 92)]),
    ]
    assert extract_pairs(lines, specs) == {"afe": "P.CP0.ABC", "date": "10-09-2026"}


def test_extract_pairs_accepts_wrapped_lines_that_start_at_or_left_of_the_value() -> None:
    specs = [LabelSpec("event", ("Event Description",)), LabelSpec("status", ("Status",))]
    wrapped = [
        TextLine.from_words([("Event", 27), ("Description:", 50), ("ORIGINAL", 100)]),
        TextLine.from_words([("DRILLING", 27)]),
    ]
    aligned = [
        TextLine.from_words([("Status", 27), (":", 124), ("Drilling", 130)]),
        TextLine.from_words([("ahead.", 130)]),
    ]
    assert extract_pairs(wrapped, specs) == {"event": "ORIGINAL DRILLING"}
    assert extract_pairs(aligned, specs) == {"status": "Drilling ahead."}
