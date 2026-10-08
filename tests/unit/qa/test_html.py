from __future__ import annotations

from wellscope.qa.html import render_answer

BUTTON = '<button type="button" class="cite" data-source="{}">{}</button>'


def test_markdown_becomes_html_with_citation_buttons() -> None:
    html = render_answer("**250,000.00** USD [S1]\n\n- first [S1, S2]", {"S1", "S2"})
    assert "<strong>250,000.00</strong>" in html
    assert BUTTON.format("S1", "S1") in html
    assert BUTTON.format("S2", "S2") in html
    assert html.count('class="cite"') == 3


def test_tables_render() -> None:
    html = render_answer("| a | b |\n| --- | --- |\n| 1 | 2 |", set())
    assert "<table>" in html
    assert "<td>1</td>" in html


def test_markup_links_and_images_never_reach_the_page() -> None:
    html = render_answer(
        "<script>alert(1)</script> [x](javascript:alert(1)) ![i](http://x/y.png) "
        '<img src=x onerror="alert(1)">',
        set(),
    )
    assert "<script" not in html
    assert "<a " not in html
    assert "<img" not in html
    assert "href" not in html


def test_unknown_citations_are_dropped() -> None:
    assert "S9" not in render_answer("value [S9]", {"S1"})
