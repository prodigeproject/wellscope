"""Command-line interface: ``wellscope <command>``."""

from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.table import Table

from wellscope import __version__
from wellscope.bootstrap import index_projector
from wellscope.config import get_settings
from wellscope.doctor import run_checks
from wellscope.observability import configure_logging
from wellscope.pipeline import IngestResult, run_ingest

app = typer.Typer(
    help="WellScope: grounded Q&A over daily drilling and geological well reports.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _show_version(value: bool) -> None:
    if value:
        console.print(f"wellscope {__version__}")
        raise typer.Exit


@app.callback()
def _root(
    version: bool = typer.Option(
        False, "--version", callback=_show_version, is_eager=True, help="Show the version."
    ),
) -> None:
    """WellScope command group."""


@app.command()
def doctor(
    strict: bool = typer.Option(False, help="Exit with status 1 when an error check fails."),
) -> None:
    """Check configuration, data folders and index state without printing secrets."""
    checks = run_checks(get_settings())
    table = Table("check", "status", "detail")
    for check in checks:
        status = "[green]ok[/]" if check.ok else f"[yellow]{check.severity}[/]"
        table.add_row(check.id, status, check.detail)
    console.print(table)
    failed = [check for check in checks if not check.ok and check.severity == "error"]
    if strict and failed:
        raise typer.Exit(code=1)


@app.command()
def ingest() -> None:
    """Parse every PDF and DOCX under the data folder, then rebuild the search index."""
    settings = get_settings()
    configure_logging("WARNING")
    console.print(f"Ingesting [bold]{settings.data_dir}[/] -> [bold]{settings.output_dir}[/]")
    _print_ingest(run_ingest(settings, index_projector(settings)))


def _print_ingest(result: IngestResult) -> None:
    manifest = result.manifest
    table = Table("document", "type", "report", "date", "pages", "quality")
    for document in manifest.documents:
        colour = "green" if document.quality_status == "ok" else "yellow"
        table.add_row(
            document.doc_id,
            document.doc_type.value,
            str(document.report_number or "-"),
            str(document.report_date or "-"),
            str(document.page_count),
            f"[{colour}]{document.quality_status}[/]",
        )
    console.print(table)
    if manifest.glossary is not None:
        console.print(f"Glossary: {manifest.glossary.entries} entries")
    for item in manifest.quarantined:
        console.print(f"[red]Quarantined[/] {item.source_file}: {item.reason} ({item.detail})")
    for note in result.notes:
        console.print(f"[dim]{note}[/]")
    console.print(f"Index version {manifest.index_version} in {result.duration_s:.1f}s")


def main() -> None:
    """Console entry point; forces UTF-8 output so Windows consoles never crash on symbols."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
    app()
