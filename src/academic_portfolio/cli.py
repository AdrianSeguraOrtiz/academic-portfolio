from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from academic_portfolio.cv import CVOutput, generate_cv
from academic_portfolio.loader import load_data
from academic_portfolio.resolver import PortfolioResolver
from academic_portfolio.site import generate_site


app = typer.Typer(help="Generate portfolio outputs from structured YAML data.")
data_app = typer.Typer(help="Inspect and validate loaded portfolio data.")
cv_app = typer.Typer(help="Generate CV outputs.")
site_app = typer.Typer(help="Generate static website outputs.")
app.add_typer(data_app, name="data")
app.add_typer(cv_app, name="cv")
app.add_typer(site_app, name="site")

console = Console()


@data_app.command("summary")
def data_summary(data_dir: Path = typer.Option(Path("data"), help="Portfolio data directory.")) -> None:
    """Print a compact summary of the YAML data files."""

    loaded_data = load_data(data_dir)

    table = Table(title=f"Portfolio data summary ({loaded_data.file_count} YAML files)")
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Top-level groups")

    for path, groups in loaded_data.top_level_groups.items():
        table.add_row(path, ", ".join(groups))

    console.print(table)


@data_app.command("resolve")
def data_resolve(
    record_id: str,
    data_dir: Path = typer.Option(Path("data"), help="Portfolio data directory."),
) -> None:
    """Print the location and outgoing references for a record ID."""

    resolver = PortfolioResolver.from_data_dir(data_dir)
    pointer = resolver.pointer(record_id)

    console.print(f"[bold]{pointer.record_id}[/bold] {pointer.label}")
    console.print(f"{pointer.file_path} / {pointer.group} / index {pointer.index}")

    references = resolver.reference_pointers_for(pointer.record)
    if not references:
        console.print("No outgoing references.")
        return

    table = Table(title="Outgoing references")
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("ID", no_wrap=True)
    table.add_column("Record")
    table.add_column("Location")

    for field, referenced_pointers in references.items():
        if not referenced_pointers:
            table.add_row(field, "-", "-", "-")
            continue

        for referenced_pointer in referenced_pointers:
            table.add_row(
                field,
                referenced_pointer.record_id,
                referenced_pointer.label,
                f"{referenced_pointer.file_path} / {referenced_pointer.group}",
            )

    console.print(table)


@cv_app.command("generate")
def cv_generate(
    model: str = typer.Option("academic_rich", help="CV model name or TOML path."),
    output_format: str = typer.Option("pdf", "--format", help="Output format: pdf or html."),
    pages: int | None = typer.Option(
        None,
        "--pages",
        min=1,
        help="Optional page limit for sober CV output.",
    ),
    output_dir: Path = typer.Option(Path("build/cv"), help="Output directory."),
    data_dir: Path = typer.Option(Path("data"), help="Portfolio data directory."),
    model_dir: Path = typer.Option(Path("cv_models"), help="CV model directory."),
    template_dir: Path = typer.Option(Path("templates/cv"), help="CV template directory."),
    static_dir: Path = typer.Option(Path("assets/cv"), help="CV static assets directory."),
) -> None:
    """Generate a CV from a configured model."""

    output = generate_cv(
        model=model,
        output_dir=output_dir,
        output_format=output_format,
        page_limit=pages,
        data_dir=data_dir,
        model_dir=model_dir,
        template_dir=template_dir,
        static_dir=static_dir,
    )
    console.print(f"Generated [bold]{output.model.title}[/bold]: {output.output_path}")
    if output.output_path != output.html_path:
        console.print(f"Intermediate HTML: {output.html_path}")
    page_status = _cv_page_status(output)
    if page_status:
        console.print(page_status)
    fit_status = _cv_fit_status(output)
    if fit_status:
        console.print(fit_status)


def _cv_page_status(output: CVOutput) -> str:
    if output.page_count is None:
        return ""
    if output.page_limit is None:
        return f"Pages: {output.page_count}"
    return f"Pages: {output.page_count}/{output.page_limit}"


def _cv_fit_status(output: CVOutput) -> str:
    if output.page_count is None or output.fit_status in {"not_checked", "not_limited"}:
        return ""

    compression_stage = output.model.layout.get("compression_stage")
    if compression_stage:
        return f"Fit status: {output.fit_status} ({compression_stage})"
    return f"Fit status: {output.fit_status}"


@site_app.command("generate")
def site_generate(
    output_dir: Path = typer.Option(Path("build/site"), help="Output directory."),
    data_dir: Path = typer.Option(Path("data"), help="Portfolio data directory."),
    template_dir: Path = typer.Option(Path("templates/site"), help="Site template directory."),
    static_dir: Path = typer.Option(Path("assets/site"), help="Site static assets directory."),
    refresh_github: bool = typer.Option(
        True,
        "--refresh-github/--no-refresh-github",
        help="Fetch public GitHub repository statistics for software projects.",
    ),
    refresh_packages: bool = typer.Option(
        True,
        "--refresh-packages/--no-refresh-packages",
        help="Fetch package registry and download statistics for software packages.",
    ),
    github_cache_path: Path = typer.Option(
        Path("build/cache/github_repositories.json"),
        help="Local cache for GitHub repository statistics.",
    ),
    package_cache_path: Path = typer.Option(
        Path("build/cache/software_packages.json"),
        help="Local cache for package registry and download statistics.",
    ),
) -> None:
    """Generate the static personal website."""

    output = generate_site(
        output_dir=output_dir,
        data_dir=data_dir,
        template_dir=template_dir,
        static_dir=static_dir,
        refresh_github=refresh_github,
        github_cache_path=github_cache_path,
        refresh_packages=refresh_packages,
        package_cache_path=package_cache_path,
    )
    console.print(f"Generated [bold]site[/bold]: {output.output_path}")


@app.callback()
def main() -> None:
    """Academic portfolio command line interface."""
