from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.pdf_canvas import PdfCanvas, pdf_canvas
from wellscope.ingestion.pdf.grid import Section, find_sections, read_grid, text_blocks
from wellscope.ingestion.pdf.layout import PageLayout, load_layout
from wellscope.ingestion.pdf.templates import GridSpec, SectionSpec

SECTIONS = (
    SectionSpec(name="status", kind="kv", titles=("STATUS",)),
    SectionSpec(name="craft", header_rows=1, split_lines=True, titles=("SUPPORT CRAFT",)),
    SectionSpec(name="remarks", kind="remarks", titles=("REMARKS",)),
)


def box(canvas: PdfCanvas, x0: float, top: float, x1: float, bottom: float) -> None:
    canvas.line(x0, top, x1, top)
    canvas.line(x0, bottom, x1, bottom)
    canvas.line(x0, top, x0, bottom)
    canvas.line(x1, top, x1, bottom)


@pytest.fixture(scope="module")
def form(tmp_path_factory: pytest.TempPathFactory) -> PageLayout:
    path: Path = tmp_path_factory.mktemp("grid") / "form.pdf"
    with pdf_canvas(path) as canvas:
        box(canvas, 20, 20, 300, 35)
        canvas.text(130, 23, "STATUS")
        box(canvas, 20, 35, 300, 75)
        canvas.text(24, 40, "Current status : Drilling ahead")
        canvas.text(24, 52, "24 hr summary : Drilled to TD.")
        box(canvas, 20, 75, 300, 90)
        canvas.text(110, 78, "SUPPORT CRAFT")
        box(canvas, 20, 90, 150, 105)
        canvas.text(24, 93, "Name")
        box(canvas, 150, 90, 300, 105)
        canvas.text(154, 93, "Comments")
        box(canvas, 20, 105, 150, 145)
        canvas.text(24, 108, "Vessel A")
        canvas.text(24, 120, "Vessel B")
        box(canvas, 150, 105, 300, 145)
        canvas.text(154, 108, "Standby")
        canvas.text(154, 120, "Enroute")
        canvas.text(154, 131, "to location")
        box(canvas, 20, 145, 300, 160)
        canvas.text(24, 148, "Remarks")
        box(canvas, 320, 20, 400, 35)
        canvas.text(324, 23, "Phase")
        box(canvas, 400, 20, 480, 35)
        canvas.text(404, 23, "Days")
        box(canvas, 320, 35, 400, 50)
        canvas.text(324, 38, "D12")
        box(canvas, 400, 35, 480, 50)
        canvas.text(404, 38, "71.50")
    return load_layout(path)[0]


def test_find_sections_detects_titles_case_sensitively(form: PageLayout) -> None:
    names = [section.name for section in find_sections([form], SECTIONS)]
    assert names == ["status", "craft"]


def test_section_region_ends_at_the_next_title(form: PageLayout) -> None:
    status = find_sections([form], SECTIONS)[0]
    assert status.text() == "Current status : Drilling ahead\n24 hr summary : Drilled to TD."


def test_split_lines_rows_merge_wrapped_continuations(form: PageLayout) -> None:
    craft = find_sections([form], SECTIONS)[1]
    assert craft.rows()[:3] == [
        ["Name", "Comments"],
        ["Vessel A", "Standby"],
        ["Vessel B", "Enroute to location"],
    ]


def test_read_grid_returns_header_and_aligned_value_rows(form: PageLayout) -> None:
    assert read_grid(form, GridSpec(name="g", header=("Phase", "Days"))) == [
        ["Phase", "Days"],
        ["D12", "71.50"],
    ]


def test_read_grid_is_empty_when_the_header_is_absent(form: PageLayout) -> None:
    assert read_grid(form, GridSpec(name="g", header=("Missing",))) == []


def test_text_blocks_keep_each_cell_separate(form: PageLayout) -> None:
    blocks = [[line.text for line in block] for block in text_blocks(form, merged_regions=[])]
    assert ["Current status : Drilling ahead", "24 hr summary : Drilled to TD."] in blocks
    assert ["Phase"] in blocks


HEADER_SECTIONS = (
    SectionSpec(name="casing", header_rows=2, titles=("CASING",)),
    SectionSpec(name="tops", header_rows=3, titles=("TOPS",)),
    SectionSpec(name="people", header_rows=2, titles=("PEOPLE",)),
    SectionSpec(name="shows", header_rows=2, titles=("SHOWS",)),
)


def cells(
    canvas: PdfCanvas, top: float, bottom: float, spans: list[tuple[float, float, str]]
) -> None:
    for x0, x1, text in spans:
        box(canvas, x0, top, x1, bottom)
        if text:
            canvas.text(x0 + 3, top + 3, text)


@pytest.fixture(scope="module")
def headed(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Section]:
    path: Path = tmp_path_factory.mktemp("headers") / "tables.pdf"
    with pdf_canvas(path) as canvas:
        cells(canvas, 20, 35, [(20, 320, "CASING")])
        cells(
            canvas,
            35,
            50,
            [(20, 80, "HOLE"), (80, 200, "INTERVAL m"), (200, 260, "SHOE m"), (260, 320, "LOT")],
        )
        cells(
            canvas,
            50,
            65,
            [
                (20, 80, "17-1/2"),
                (80, 140, "1129.00"),
                (140, 200, "1860.00"),
                (200, 260, "1858.70"),
                (260, 320, "14.94"),
            ],
        )
        cells(canvas, 100, 115, [(20, 200, "TOPS")])
        cells(canvas, 115, 145, [(20, 80, "TOP")])
        cells(canvas, 115, 130, [(80, 200, "Prognosis")])
        cells(canvas, 130, 145, [(80, 140, "MDDF"), (140, 200, "TVDSS")])
        cells(canvas, 145, 160, [(20, 80, "Top I"), (80, 140, "693.0"), (140, 200, "663.0")])
        cells(canvas, 200, 215, [(20, 200, "PEOPLE")])
        cells(canvas, 215, 230, [(20, 200, "Total people: 140")])
        cells(canvas, 230, 245, [(20, 110, "Company"), (110, 200, "# People")])
        cells(canvas, 245, 260, [(20, 110, "ACME"), (110, 200, "3")])
        cells(canvas, 300, 315, [(20, 260, "SHOWS")])
        cells(canvas, 315, 345, [(20, 80, "Depth"), (200, 260, "Odor")])
        cells(canvas, 315, 330, [(80, 200, "Fluor.")])
        cells(canvas, 330, 345, [(80, 140, "Int."), (140, 200, "Col.")])
    page = load_layout(path)[0]
    return {section.name: section for section in find_sections([page], HEADER_SECTIONS)}


def test_a_header_cell_spanning_columns_names_each_part(headed: dict[str, Section]) -> None:
    header = headed["casing"].header()
    assert header.rows == 1
    assert header.columns == ("HOLE", "INTERVAL m [1/2]", "INTERVAL m [2/2]", "SHOE m", "LOT")


def test_two_level_headers_are_flattened_per_column(headed: dict[str, Section]) -> None:
    header = headed["tops"].header()
    assert header.rows == 2
    assert header.columns == ("TOP", "Prognosis MDDF", "Prognosis TVDSS")


def test_caption_rows_count_as_header_but_do_not_name_columns(headed: dict[str, Section]) -> None:
    header = headed["people"].header()
    assert header.rows == 2
    assert header.columns == ("Company", "# People")


def test_header_cells_spanning_both_rows_stay_columns_without_data(
    headed: dict[str, Section],
) -> None:
    header = headed["shows"].header()
    assert header.rows == 2
    assert header.columns == ("Depth", "Fluor. Int.", "Fluor. Col.", "Odor")
