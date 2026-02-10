"""CLI interface for LinkedScout."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from beartype import beartype
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from linkedscout.config import Settings
from linkedscout.models.search import JobType, SearchCriteria, TimeFilter, WorkModel
from linkedscout.services.alert_service import AlertService
from linkedscout.services.job_service import JobService

app = typer.Typer(
    name="linkedscout",
    help="Tool to collect job offers from LinkedIn based on search criteria.",
    no_args_is_help=True,
)

alerts_app = typer.Typer(
    name="alerts",
    help="Manage saved job alerts.",
    no_args_is_help=True,
)
app.add_typer(alerts_app, name="alerts")

console = Console()


@beartype
def _parse_time_filter(value: str) -> TimeFilter:
    """Parse time filter from CLI argument."""
    mapping = {
        "24h": TimeFilter.PAST_24H,
        "1d": TimeFilter.PAST_24H,
        "7d": TimeFilter.PAST_WEEK,
        "1w": TimeFilter.PAST_WEEK,
        "30d": TimeFilter.PAST_MONTH,
        "1m": TimeFilter.PAST_MONTH,
        "any": TimeFilter.ANY_TIME,
    }
    return mapping.get(value.lower(), TimeFilter.PAST_WEEK)


@beartype
def _get_settings(
    alerts_file: Path | None = None,
    output_dir: Path | None = None,
    db_path: Path | None = None,
) -> Settings:
    """Create settings with optional overrides."""
    settings = Settings()
    if alerts_file:
        settings = Settings(
            alerts_file=alerts_file,
            output_dir=settings.output_dir,
            db_path=settings.db_path,
        )
    if output_dir:
        settings = Settings(
            alerts_file=settings.alerts_file,
            output_dir=output_dir,
            db_path=settings.db_path,
        )
    if db_path:
        settings = Settings(
            alerts_file=settings.alerts_file,
            output_dir=settings.output_dir,
            db_path=db_path,
        )
    return settings


@app.command()
@beartype
def search(
    keywords: Annotated[str, typer.Option("--keywords", "-k", help="Search keywords")],
    location: Annotated[str, typer.Option("--location", "-l", help="Location")] = "",
    time: Annotated[
        str, typer.Option("--time", "-t", help="Time filter (24h, 7d, 30d, any)")
    ] = "7d",
    remote: Annotated[
        bool, typer.Option("--remote", "-r", help="Only remote jobs")
    ] = False,
    hybrid: Annotated[bool, typer.Option("--hybrid", help="Only hybrid jobs")] = False,
    on_site: Annotated[
        bool, typer.Option("--on-site", help="Only on-site jobs")
    ] = False,
    full_time: Annotated[
        bool, typer.Option("--full-time", "-f", help="Full-time only")
    ] = False,
    contract: Annotated[
        bool, typer.Option("--contract", "-c", help="Contract/freelance only")
    ] = False,
    max_results: Annotated[
        int, typer.Option("--max", "-m", help="Maximum results")
    ] = 100,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output JSON file path")
    ] = None,
) -> None:
    """Search for jobs on LinkedIn."""
    # Build work models filter
    work_models: list[WorkModel] = []
    if remote:
        work_models.append(WorkModel.REMOTE)
    if hybrid:
        work_models.append(WorkModel.HYBRID)
    if on_site:
        work_models.append(WorkModel.ON_SITE)

    # Build job types filter
    job_types: list[JobType] = []
    if full_time:
        job_types.append(JobType.FULL_TIME)
    if contract:
        job_types.append(JobType.CONTRACT)

    criteria = SearchCriteria(
        keywords=keywords,
        location=location,
        time_filter=_parse_time_filter(time),
        work_models=work_models,
        job_types=job_types,
        max_results=max_results,
    )

    service = JobService()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Searching LinkedIn jobs...", total=None)
        jobs = asyncio.run(service.search(criteria))

    if not jobs:
        console.print("[yellow]No jobs found matching your criteria.[/yellow]")
        return

    # Display results table
    table = Table(title=f"Found {len(jobs)} jobs")
    table.add_column("Title", style="cyan", no_wrap=True, max_width=40)
    table.add_column("Company", style="green", max_width=25)
    table.add_column("Location", style="yellow", max_width=20)
    table.add_column("Posted", style="magenta")

    for job in jobs[:20]:  # Show first 20 in table
        posted = ""
        if job.posted_at:
            posted = job.posted_at.strftime("%Y-%m-%d")
        table.add_row(job.title, job.company, job.location, posted)

    console.print(table)

    if len(jobs) > 20:
        console.print(f"[dim]... and {len(jobs) - 20} more jobs[/dim]")

    # Save to JSON if requested
    if output:
        service.save_to_json(jobs, output_path=output)
        console.print(f"\n[green]Saved {len(jobs)} jobs to {output}[/green]")


@alerts_app.command("list")
@beartype
def list_alerts(
    alerts_file: Annotated[
        Path | None, typer.Option("--file", "-f", help="Alerts file path")
    ] = None,
) -> None:
    """List all saved alerts."""
    settings = _get_settings(alerts_file=alerts_file)
    service = AlertService(settings)
    alerts = service.list_alerts()

    if not alerts:
        console.print("[yellow]No alerts found.[/yellow]")
        console.print(
            "[dim]Create one with: linkedscout alerts create <name> --keywords '...'[/dim]"
        )
        return

    table = Table(title="Saved Alerts")
    table.add_column("Name", style="cyan")
    table.add_column("Keywords", style="green")
    table.add_column("Location", style="yellow")
    table.add_column("Time", style="magenta")
    table.add_column("Enabled", style="blue")

    time_labels = {
        TimeFilter.PAST_24H: "24h",
        TimeFilter.PAST_WEEK: "7d",
        TimeFilter.PAST_MONTH: "30d",
        TimeFilter.ANY_TIME: "any",
    }

    for alert in alerts:
        status = "[green]Yes[/green]" if alert.enabled else "[red]No[/red]"
        time_label = time_labels.get(alert.criteria.time_filter, "7d")
        table.add_row(
            alert.name,
            alert.criteria.keywords,
            alert.criteria.location or "-",
            time_label,
            status,
        )

    console.print(table)


@alerts_app.command("create")
@beartype
def create_alert(
    name: Annotated[str, typer.Argument(help="Alert name")],
    keywords: Annotated[str, typer.Option("--keywords", "-k", help="Search keywords")],
    location: Annotated[str, typer.Option("--location", "-l", help="Location")] = "",
    time: Annotated[
        str, typer.Option("--time", "-t", help="Time filter (24h, 7d, 30d, any)")
    ] = "7d",
    remote: Annotated[
        bool, typer.Option("--remote", "-r", help="Only remote jobs")
    ] = False,
    hybrid: Annotated[bool, typer.Option("--hybrid", help="Only hybrid jobs")] = False,
    full_time: Annotated[
        bool, typer.Option("--full-time", help="Full-time only")
    ] = False,
    max_results: Annotated[
        int, typer.Option("--max", "-m", help="Maximum results")
    ] = 100,
    alerts_file: Annotated[
        Path | None, typer.Option("--file", help="Alerts file path")
    ] = None,
) -> None:
    """Create a new alert."""
    settings = _get_settings(alerts_file=alerts_file)
    service = AlertService(settings)

    # Check if alert already exists
    if service.get_alert(name):
        console.print(f"[red]Alert '{name}' already exists.[/red]")
        raise typer.Exit(1)

    # Build work models filter
    work_models: list[WorkModel] = []
    if remote:
        work_models.append(WorkModel.REMOTE)
    if hybrid:
        work_models.append(WorkModel.HYBRID)

    # Build job types filter
    job_types: list[JobType] = []
    if full_time:
        job_types.append(JobType.FULL_TIME)

    alert = service.create_alert(
        name=name,
        keywords=keywords,
        location=location,
        time_filter=_parse_time_filter(time),
        work_models=work_models,
        job_types=job_types,
        max_results=max_results,
    )

    console.print(f"[green]Created alert '{alert.name}'[/green]")
    console.print(f"[dim]Saved to: {service.get_alerts_file()}[/dim]")


@alerts_app.command("delete")
@beartype
def delete_alert(
    name: Annotated[str, typer.Argument(help="Alert name to delete")],
    alerts_file: Annotated[
        Path | None, typer.Option("--file", help="Alerts file path")
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Skip confirmation")
    ] = False,
) -> None:
    """Delete an alert."""
    settings = _get_settings(alerts_file=alerts_file)
    service = AlertService(settings)

    if not service.get_alert(name):
        console.print(f"[red]Alert '{name}' not found.[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Delete alert '{name}'?")
        if not confirm:
            raise typer.Abort()

    service.delete_alert(name)
    console.print(f"[green]Deleted alert '{name}'[/green]")


@alerts_app.command("run")
@beartype
def run_alerts(
    name: Annotated[
        str | None, typer.Option("--name", "-n", help="Run specific alert")
    ] = None,
    all_alerts: Annotated[
        bool, typer.Option("--all", "-a", help="Run all enabled alerts")
    ] = False,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output JSON file path")
    ] = None,
    alerts_file: Annotated[
        Path | None, typer.Option("--file", help="Alerts file path")
    ] = None,
) -> None:
    """Run saved alerts and fetch matching jobs."""
    if not name and not all_alerts:
        console.print("[red]Specify --name or --all[/red]")
        raise typer.Exit(1)

    settings = _get_settings(alerts_file=alerts_file)
    alert_service = AlertService(settings)
    job_service = JobService(settings)

    # Get alerts to run
    if name:
        alert = alert_service.get_alert(name)
        if not alert:
            console.print(f"[red]Alert '{name}' not found.[/red]")
            raise typer.Exit(1)
        alerts_to_run = [alert]
    else:
        alerts_to_run = alert_service.get_enabled_alerts()

    if not alerts_to_run:
        console.print("[yellow]No alerts to run.[/yellow]")
        return

    all_jobs = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for alert in alerts_to_run:
            task = progress.add_task(f"Running alert '{alert.name}'...", total=None)
            jobs = asyncio.run(job_service.run_alert(alert))
            all_jobs.extend(jobs)
            progress.update(
                task, description=f"[green]'{alert.name}': {len(jobs)} jobs[/green]"
            )

    # Deduplicate by job ID
    seen_ids: set[str] = set()
    unique_jobs = []
    for job in all_jobs:
        if job.id not in seen_ids:
            seen_ids.add(job.id)
            unique_jobs.append(job)

    # Sort by date (most recent first), using .timestamp() to avoid
    # TypeError from mixing naive and aware datetimes
    unique_jobs.sort(
        key=lambda j: (
            (j.posted_at or j.scraped_at).timestamp()
            if (j.posted_at or j.scraped_at)
            else 0.0
        ),
        reverse=True,
    )

    console.print(f"\n[bold]Found {len(unique_jobs)} unique jobs[/bold]")

    # Display summary table
    if unique_jobs:
        table = Table(title="Recent Jobs")
        table.add_column("Title", style="cyan", max_width=40)
        table.add_column("Company", style="green", max_width=25)
        table.add_column("Location", style="yellow", max_width=20)
        table.add_column("Posted", style="magenta")

        for job in unique_jobs[:10]:
            posted = ""
            if job.posted_at:
                posted = job.posted_at.strftime("%Y-%m-%d")
            table.add_row(job.title, job.company, job.location, posted)

        console.print(table)

        if len(unique_jobs) > 10:
            console.print(f"[dim]... and {len(unique_jobs) - 10} more jobs[/dim]")

    # Save to JSON if requested
    if output and unique_jobs:
        job_service.save_to_json(unique_jobs, output_path=output)
        console.print(f"\n[green]Saved {len(unique_jobs)} jobs to {output}[/green]")


@alerts_app.command("enable")
@beartype
def enable_alert(
    name: Annotated[str, typer.Argument(help="Alert name")],
    alerts_file: Annotated[
        Path | None, typer.Option("--file", help="Alerts file path")
    ] = None,
) -> None:
    """Enable an alert."""
    settings = _get_settings(alerts_file=alerts_file)
    service = AlertService(settings)

    alert = service.update_alert(name, enabled=True)
    if not alert:
        console.print(f"[red]Alert '{name}' not found.[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Enabled alert '{name}'[/green]")


@alerts_app.command("disable")
@beartype
def disable_alert(
    name: Annotated[str, typer.Argument(help="Alert name")],
    alerts_file: Annotated[
        Path | None, typer.Option("--file", help="Alerts file path")
    ] = None,
) -> None:
    """Disable an alert."""
    settings = _get_settings(alerts_file=alerts_file)
    service = AlertService(settings)

    alert = service.update_alert(name, enabled=False)
    if not alert:
        console.print(f"[red]Alert '{name}' not found.[/red]")
        raise typer.Exit(1)

    console.print(f"[yellow]Disabled alert '{name}'[/yellow]")


@alerts_app.command("migrate")
@beartype
def migrate_alerts(
    from_dir: Annotated[Path, typer.Option("--from", help="Source alerts directory")],
    to_file: Annotated[Path, typer.Option("--to", help="Target alerts.yaml file")],
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite existing file")
    ] = False,
) -> None:
    """Migrate alerts from directory-based storage to single file.

    This is a one-time migration command to convert from the old format
    (multiple YAML files in alerts/ directory) to the new format
    (single alerts.yaml file).
    """
    # Check if source directory exists
    if not from_dir.exists():
        console.print(f"[red]Source directory not found: {from_dir}[/red]")
        raise typer.Exit(1)

    # Check if target file exists
    if to_file.exists() and not force:
        console.print(f"[red]Target file already exists: {to_file}[/red]")
        console.print("[dim]Use --force to overwrite[/dim]")
        raise typer.Exit(1)

    # Remove existing target file if force is enabled
    if to_file.exists() and force:
        to_file.unlink()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Migrating alerts...", total=None)
            count = AlertService.migrate_from_directory(from_dir, to_file)

        console.print(
            f"[green]Successfully migrated {count} alerts to {to_file}[/green]"
        )
        console.print(f"[dim]You can now delete the old directory: {from_dir}[/dim]")

    except (NotADirectoryError, ValueError, OSError) as e:
        console.print(f"[red]Migration failed: {e}[/red]")
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
