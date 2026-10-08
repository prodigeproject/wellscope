from __future__ import annotations

import pytest

from wellscope.ingestion.pdf.dgos import paired_labels


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Depth m MDDF /m TVDSS", ["Depth m MDDF", "Depth m TVDSS"]),
        ("AFE Depth m MDDF /m TVDSS", ["AFE Depth m MDDF", "AFE Depth m TVDSS"]),
        ("Days / Cost", ["Days", "Cost"]),
    ],
)
def test_paired_header_labels_each_value(label: str, expected: list[str]) -> None:
    assert paired_labels(label, 2) == expected


def test_headers_that_do_not_split_evenly_keep_one_label() -> None:
    assert paired_labels("Depth", 2) == ["Depth", "Depth"]
