"""Command-line interface: ``wellscope <command>``."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from wellscope import __version__
from wellscope.bootstrap import index_projector, models, qa_service, web_app
from wellscope.config import get_settings
from wellscope.doctor import model_checks, run_checks
from wellscope.domain.schemas import json_schemas
from wellscope.errors import WellScopeError
from wellscope.evals.golden import load_golden
from wellscope.evals.report import summarize
from wellscope.evals.runner import run_eval, save_run
from wellscope.evals.scoring import ItemResult
from wellscope.observability import configure_logging
from wellscope.pipeline import IngestResult, run_ingest
from wellscope.qa.service import Answer

DEFAULT_GOLDEN = Path("evals/private/golden.yaml")
DEFAULT_REPORTS = Path("reports")
PRIVATE_RUNS = Path("evals/private/runs")
DEFAULT_SCHEMAS = Path("docs/schemas")
MAX_WORKERS = 8

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
    version: Annotated[
        bool,
        typer.Option("--version", callback=_show_version, is_eager=True, help="Show the version."),
    ] = False,
) -> None:
    """WellScope command group."""


@app.command()
def doctor(
    strict: Annotated[
        bool, typer.Option(help="Exit with status 1 when an error check fails.")
    ] = False,
    online: Annotated[
        bool, typer.Option(help="Also call each configured model once to check access.")
    ] = False,
) -> None:
    """Check configuration, data folders, the index and (online) model access; no secrets shown."""
    settings = get_settings()
    checks = run_checks(settings)
    if online:
        built = models(settings)
        chat = {"chat": built.chat, "analyzer": built.analyzer}
        configured = {role: model for role, model in chat.items() if model is not None}
        checks += model_checks(configured, built.embedder)
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
    try:
        result = run_ingest(settings, index_projector(settings))
    except WellScopeError as error:
        console.print(f"[red]Ingest stopped:[/] {error} ({error.code})")
        raise typer.Exit(code=1) from error
    _print_ingest(result)


@app.command()
def serve(
    host: Annotated[str | None, typer.Option(help="Interface to bind.")] = None,
    port: Annotated[int | None, typer.Option(help="Port to listen on.")] = None,
) -> None:
    """Start the web app (http://127.0.0.1:8000 by default); the index reloads after ingest."""
    import uvicorn  # noqa: PLC0415 - only this command needs the server

    settings = get_settings()
    configure_logging(settings.log_level)
    if host is not None or port is not None:
        overrides = {"host": host or settings.host, "port": port or settings.port}
        settings = settings.model_copy(update=overrides)
    console.print(f"WellScope on [bold]http://{settings.host}:{settings.port}[/] (Ctrl+C to stop)")
    uvicorn.run(
        web_app(settings),
        host=settings.host,
        port=settings.port,
        log_config=None,
        proxy_headers=False,  # the rate limiter keys on the real peer address
        server_header=False,
    )


@app.command()
def ask(
    question: Annotated[str, typer.Argument(help="A question about the reports or the glossary.")],
    as_json: Annotated[
        bool, typer.Option("--json", help="Print the whole answer as JSON.")
    ] = False,
) -> None:
    """Ask one question from the terminal (same pipeline as the web app)."""
    configure_logging("WARNING")
    answer = qa_service(get_settings()).ask(question)
    if as_json:
        console.print_json(json.dumps(asdict(answer), default=str))
    else:
        _print_answer(answer)


@app.command(name="eval")
def evaluate(
    golden: Annotated[Path, typer.Option("--set", help="Golden question set (YAML).")] = (
        DEFAULT_GOLDEN
    ),
    reports: Annotated[Path, typer.Option(help="Folder for aggregate reports.")] = DEFAULT_REPORTS,
    workers: Annotated[
        int, typer.Option(min=1, max=MAX_WORKERS, help="Questions answered in parallel.")
    ] = 4,
    only: Annotated[list[str] | None, typer.Option(help="Run only these item ids.")] = None,
) -> None:
    """Score the pipeline on a golden question set (this calls the configured models)."""
    configure_logging("WARNING")
    items = [item for item in load_golden(golden) if not only or item.id in only]
    runs = run_eval(qa_service(get_settings()), items, workers)
    results = [result for _, _, result in runs]
    _print_results(results)
    summary = summarize(results)
    overall = summary["overall"]
    console.print(f"Accuracy {overall['passed']}/{overall['total']} ({overall['rate']:.1%})")
    report = save_run(runs, summary, reports, PRIVATE_RUNS)
    console.print(f"Report: {report} (answers kept privately in {PRIVATE_RUNS})")


@app.command()
def schema(
    out: Annotated[Path, typer.Option(help="Folder for the schema files.")] = DEFAULT_SCHEMAS,
) -> None:
    """Export JSON Schemas of the JSON files that ingest writes."""
    out.mkdir(parents=True, exist_ok=True)
    for name, document in json_schemas().items():
        path = out / f"{name}.schema.json"
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n")
        console.print(f"Wrote {path}")


def _print_results(results: list[ItemResult]) -> None:
    table = Table("id", "category", "status", "verified", "result", "missing")
    for result in results:
        verdict = "[green]pass[/]" if result.passed else "[red]fail[/]"
        verified = "yes" if result.verified else "[yellow]no[/]"
        missing = "; ".join(result.missing)
        table.add_row(result.id, result.category, result.status, verified, verdict, missing)
    console.print(table)


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
