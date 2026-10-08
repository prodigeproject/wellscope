"""Command-line interface: ``wellscope <command>``."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from wellscope import __version__
from wellscope.bootstrap import index_projector, qa_service, web_app
from wellscope.config import get_settings
from wellscope.doctor import run_checks
from wellscope.observability import configure_logging
from wellscope.pipeline import IngestResult, run_ingest
from wellscope.qa.service import Answer

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


@app.command()
def serve(
    host: str | None = typer.Option(None, help="Interface to bind (default from settings)."),
    port: int | None = typer.Option(None, help="Port to listen on (default from settings)."),
) -> None:
    """Start the web app (http://127.0.0.1:8000 by default); the index reloads after ingest."""
    import uvicorn  # noqa: PLC0415 - only this command needs the server

    settings = get_settings()
    configure_logging(settings.log_level)
    if host is not None or port is not None:
        overrides = {"host": host or settings.host, "port": port or settings.port}
        settings = settings.model_copy(update=overrides)
    console.print(f"WellScope on [bold]http://{settings.host}:{settings.port}[/] (Ctrl+C to stop)")
    uvicorn.run(web_app(settings), host=settings.host, port=settings.port, log_config=None)


@app.command()
def ask(
    question: str = typer.Argument(..., help="A question about the reports or the glossary."),
    as_json: bool = typer.Option(False, "--json", help="Print the whole answer as JSON."),
) -> None:
    """Ask one question from the terminal (same pipeline as the web app)."""
    configure_logging("WARNING")
    answer = qa_service(get_settings()).ask(question)
    if as_json:
        console.print_json(json.dumps(asdict(answer), default=str))
    else:
        _print_answer(answer)


def _print_answer(answer: Answer) -> None:
    colour = {"answered": "green", "error": "red"}.get(answer.status, "yellow")
    badge = answer.status if answer.verified else f"{answer.status}, unverified"
    console.print(f"[bold {colour}]{badge}[/]")
    console.print(Markdown(answer.markdown))
    for citation in answer.citations:
        page = f" p.{citation.page}" if citation.page else ""
        console.print(f"[dim][{citation.id}] {citation.label} · {citation.section}{page}[/]")
    for caveat in answer.caveats:
        console.print(f"[yellow]Note:[/] {caveat}")
    models = ", ".join(usage.model for usage in answer.usage) or "no model"
    console.print(f"[dim]{answer.latency_ms} ms · {models} · {answer.reason}[/]")


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
