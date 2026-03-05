"""Command-line interface using Typer."""

from pathlib import Path
from typing import Optional, List
from enum import Enum

import typer
from typing_extensions import Annotated

from .main import run_validate, run_scrape
from .logger import setup_logger


class SourceType(str, Enum):
    """Source type for scraping."""
    ALL = "all"
    JIRA = "jira"
    CONFLUENCE = "confluence"


app = typer.Typer(
    name="jira-scraper",
    help="Jira/Confluence Work History Scraper - 개인 업무 이력 수집 도구",
    no_args_is_help=True,
)


@app.command()
def validate():
    """
    Validate configuration and API connections.

    Checks:
    - Configuration file syntax
    - Environment variables
    - Jira API connection
    - Confluence API connection
    """
    exit(run_validate())


@app.command()
def scrape(
    source: Annotated[
        SourceType,
        typer.Option(
            "-s", "--source",
            help="Source to scrape"
        )
    ] = SourceType.ALL,
    projects: Annotated[
        Optional[str],
        typer.Option(
            "-p", "--projects",
            help="Comma-separated list of Jira project keys (e.g., PROJ1,PROJ2)"
        )
    ] = None,
    spaces: Annotated[
        Optional[str],
        typer.Option(
            "--spaces",
            help="Comma-separated list of Confluence space keys (e.g., DEV,ARCH)"
        )
    ] = None,
    date_from: Annotated[
        Optional[str],
        typer.Option(
            "-f", "--from",
            help="Start date in YYYY-MM-DD format"
        )
    ] = None,
    date_to: Annotated[
        Optional[str],
        typer.Option(
            "-t", "--to",
            help="End date in YYYY-MM-DD format"
        )
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Count items only, don't scrape data"
        )
    ] = False,
    resume: Annotated[
        bool,
        typer.Option(
            "--resume",
            help="Resume from previous checkpoint"
        )
    ] = False,
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            help="Logging level (DEBUG, INFO, WARNING, ERROR)"
        )
    ] = "INFO",
):
    """
    Scrape Jira issues and/or Confluence pages.

    Examples:

        # Scrape everything
        $ python -m src.main scrape --all

        # Scrape Jira only
        $ python -m src.main scrape -s jira

        # Scrape specific projects
        $ python -m src.main scrape -p PROJ1,PROJ2

        # Scrape with date range
        $ python -m src.main scrape -f 2024-01-01 -t 2024-12-31

        # Dry run to count items
        $ python -m src.main scrape --dry-run

        # Resume from checkpoint
        $ python -m src.main scrape --resume
    """
    # Setup logger
    setup_logger(level=log_level)

    # Parse comma-separated values
    project_list = [p.strip() for p in projects.split(",")] if projects else None
    space_list = [s.strip() for s in spaces.split(",")] if spaces else None

    # Run scraping
    exit(run_scrape(
        source=source.value,
        projects=project_list,
        spaces=space_list,
        date_from=date_from,
        date_to=date_to,
        dry_run=dry_run,
        resume=resume,
    ))


@app.command()
def init():
    """
    Initialize configuration files interactively.

    Creates:
    - config/config.yaml (if not exists)
    - .env (if not exists)

    Guides user through setup process.
    """
    typer.echo("🚀 Initializing Jira/Confluence Scraper...")
    typer.echo()

    # Check if config exists
    config_dir = Path("config")
    config_file = config_dir / "config.yaml"

    if config_file.exists():
        overwrite = typer.confirm("config/config.yaml already exists. Overwrite?")
        if not overwrite:
            typer.echo("Skipping config.yaml creation.")
        else:
            typer.echo("TODO: Implement interactive config creation")
    else:
        typer.echo("✓ config/config.yaml exists - please edit it manually")

    # Check if .env exists
    env_file = Path(".env")
    if env_file.exists():
        overwrite = typer.confirm(".env already exists. Overwrite?")
        if not overwrite:
            typer.echo("Skipping .env creation.")
        else:
            typer.echo("TODO: Implement interactive .env creation")
    else:
        typer.echo("✓ Please create .env file from .env.example")

    typer.echo()
    typer.echo("📖 For setup instructions, see README.md")


def main():
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
