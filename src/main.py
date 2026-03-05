"""Main application entry point."""

import asyncio
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from .config import load_config, load_env_config
from .auth import AtlassianAuth
from .http_client import AtlassianClient
from .logger import setup_logger, get_logger
from .exceptions import ScraperError, ConfigValidationError, AuthenticationError

console = Console()


def print_banner():
    """Print application banner with warnings."""
    banner_text = """
[bold cyan]Jira/Confluence Work History Scraper[/bold cyan]

[yellow]⚠️  주의사항[/yellow]
• 이 도구는 개인의 업무 이력 정리를 위한 목적으로 설계되었습니다.
• 회사의 데이터 보안 정책을 확인하고 준수하십시오.
• 수집된 데이터에 기밀 정보가 포함되어 있을 수 있으니 관리에 주의하십시오.
• 본인의 업무 이력만 수집하며, 타인의 데이터는 수집하지 않습니다.
    """
    console.print(Panel(banner_text, border_style="cyan"))


async def validate_connections():
    """
    Validate API connections and configuration.

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Load configuration
        console.print("\n[cyan]Loading configuration...[/cyan]")
        config = load_config()
        env_config = load_env_config()

        console.print("✓ Configuration loaded successfully", style="green")

        # Initialize authentication
        auth = AtlassianAuth(env_config)

        # Test Jira connection
        jira_account_id = None
        if config.jira.enabled:
            console.print("\n[cyan]Testing Jira connection...[/cyan]")
            jira_client = AtlassianClient(
                base_url=config.server.jira_base_url,
                auth=auth,
                config=config.execution,
            )
            try:
                user_data = await auth.validate_jira_connection(jira_client)
                jira_account_id = user_data.get('accountId')
            finally:
                await jira_client.close()

        # Test Confluence connection
        confluence_account_id = None
        if config.confluence.enabled:
            console.print("\n[cyan]Testing Confluence connection...[/cyan]")
            confluence_client = AtlassianClient(
                base_url=config.server.confluence_base_url,
                auth=auth,
                config=config.execution,
            )
            try:
                user_data = await auth.validate_confluence_connection(confluence_client)
                confluence_account_id = user_data.get('accountId')
            finally:
                await confluence_client.close()

        # Display account ID prominently
        if jira_account_id or confluence_account_id:
            account_id = jira_account_id or confluence_account_id
            console.print(f"\n[bold yellow]📋 Your Account ID: {account_id}[/bold yellow]")
            console.print(f"[dim]→ config.yaml의 user.account_id에 이 값을 설정하세요[/dim]")

            # Check if config matches
            if config.user.account_id != account_id:
                console.print(f"[yellow]⚠️  config.yaml의 account_id ({config.user.account_id})가 실제 값과 다릅니다![/yellow]")

        console.print("\n[bold green]✓ All connections validated successfully![/bold green]")
        return True, "Validation successful"

    except ConfigValidationError as e:
        console.print(f"\n[bold red]✗ Configuration Error:[/bold red] {e}")
        return False, str(e)

    except AuthenticationError as e:
        console.print(f"\n[bold red]✗ Authentication Error:[/bold red] {e}")
        return False, str(e)

    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected Error:[/bold red] {e}")
        return False, str(e)


def run_validate():
    """Run validation command."""
    print_banner()
    success, _ = asyncio.run(validate_connections())
    return 0 if success else 1


async def run_scrape_async(
    source: str = "all",
    projects: list[str] | None = None,
    spaces: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    dry_run: bool = False,
    resume: bool = False,
):
    """
    Run scraping operation (async).

    Args:
        source: Source to scrape ("all", "jira", "confluence")
        projects: List of Jira project keys
        spaces: List of Confluence space keys
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        dry_run: Only count items, don't scrape
        resume: Resume from checkpoint
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from .jira_scraper import JiraScraper
    from .confluence_scraper import ConfluenceScraper
    from .data_processor import DataProcessor
    from .csv_exporter import CSVExporter
    from .checkpoint import CheckpointManager

    logger = get_logger()

    try:
        # Load configuration
        console.print("\n[cyan]Loading configuration...[/cyan]")
        config = load_config()
        env_config = load_env_config()

        # Override config with CLI options
        if projects:
            config.jira.projects = projects
        if spaces:
            config.confluence.spaces = spaces
        if date_from:
            config.jira.date_from = date_from
            config.confluence.date_from = date_from
        if date_to:
            config.jira.date_to = date_to
            config.confluence.date_to = date_to

        # Determine what to scrape
        scrape_jira = source in ("all", "jira") and config.jira.enabled
        scrape_confluence = source in ("all", "confluence") and config.confluence.enabled

        # Initialize components
        auth = AtlassianAuth(env_config)
        checkpoint_mgr = CheckpointManager()
        processor = DataProcessor()
        exporter = CSVExporter(config.output)

        # Check for checkpoint
        checkpoint_state = None
        if resume and checkpoint_mgr.exists():
            checkpoint_state = checkpoint_mgr.load()
            if checkpoint_state:
                console.print("[yellow]Resuming from checkpoint...[/yellow]")

        # Results
        jira_issues = []
        confluence_pages = []
        output_files = []

        # === JIRA SCRAPING ===
        if scrape_jira:
            console.print("\n[bold cyan]━━━ Jira Issues ━━━[/bold cyan]")

            jira_client = AtlassianClient(
                base_url=config.server.jira_base_url,
                auth=auth,
                config=config.execution,
            )

            try:
                scraper = JiraScraper(jira_client, config.user, config.jira)

                # Count issues (API v3 doesn't provide total)
                total_issues = await scraper.count_issues()

                if total_issues is not None:
                    console.print(f"Found {total_issues} issues")
                else:
                    console.print("Counting issues (API v3 doesn't provide total upfront)...")

                if dry_run:
                    console.print("[dim]Dry run - skipping collection[/dim]")
                else:
                    # Scrape issues
                    if total_issues is not None:
                        # Known total: use progress bar
                        with Progress(
                            SpinnerColumn(),
                            TextColumn("[progress.description]{task.description}"),
                            BarColumn(),
                            TaskProgressColumn(),
                            console=console,
                        ) as progress:
                            task = progress.add_task(
                                "Collecting Jira issues...",
                                total=total_issues
                            )
                            jira_issues = await scraper.scrape_all()
                            progress.update(task, completed=total_issues)
                    else:
                        # Unknown total: use spinner only
                        with Progress(
                            SpinnerColumn(),
                            TextColumn("[progress.description]{task.description}"),
                            console=console,
                        ) as progress:
                            task = progress.add_task("Collecting Jira issues...")
                            jira_issues = await scraper.scrape_all()
                            progress.update(task, description=f"✓ Collected {len(jira_issues)} Jira issues")

            finally:
                await jira_client.close()

        # === CONFLUENCE SCRAPING ===
        if scrape_confluence:
            console.print("\n[bold cyan]━━━ Confluence Pages ━━━[/bold cyan]")

            confluence_client = AtlassianClient(
                base_url=config.server.confluence_base_url,
                auth=auth,
                config=config.execution,
            )

            try:
                scraper = ConfluenceScraper(confluence_client, config.user, config.confluence)

                # Count pages
                total_pages = await scraper.count_pages()
                console.print(f"Found {total_pages} pages")

                if dry_run:
                    console.print("[dim]Dry run - skipping collection[/dim]")
                else:
                    # Scrape pages
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        console=console,
                    ) as progress:
                        task = progress.add_task("Collecting Confluence pages...")
                        confluence_pages = await scraper.scrape_all()
                        progress.update(task, description=f"✓ Collected {len(confluence_pages)} Confluence pages")

            finally:
                await confluence_client.close()

        # === DATA PROCESSING & EXPORT ===
        if not dry_run:
            console.print("\n[bold cyan]━━━ Processing & Export ━━━[/bold cyan]")

            # Process data
            if jira_issues:
                jira_issues = processor.process_jira_data(jira_issues)
                filepath = exporter.export_jira(jira_issues)
                if filepath:
                    output_files.append(("Jira issues", filepath, len(jira_issues)))

            if confluence_pages:
                confluence_pages = processor.process_confluence_data(confluence_pages)
                filepath = exporter.export_confluence(confluence_pages)
                if filepath:
                    output_files.append(("Confluence pages", filepath, len(confluence_pages)))

            # Generate summary
            if jira_issues or confluence_pages:
                summary = processor.generate_work_summary(jira_issues, confluence_pages)
                filepath = exporter.export_summary(summary)
                if filepath:
                    output_files.append(("Work summary", filepath, len(summary)))

            # Clear checkpoint on success
            checkpoint_mgr.clear()

            # Display results
            console.print("\n[bold green]✓ Scraping completed successfully![/bold green]")
            console.print(f"\n[bold]Summary:[/bold]")
            if jira_issues:
                console.print(f"  • Jira issues collected: {len(jira_issues)}")
            if confluence_pages:
                console.print(f"  • Confluence pages collected: {len(confluence_pages)}")

            console.print(f"\n[bold]Output files:[/bold]")
            for name, filepath, count in output_files:
                console.print(f"  • {filepath.name} ({count} rows)")

        return True

    except ConfigValidationError as e:
        console.print(f"\n[bold red]✗ Configuration Error:[/bold red] {e}")
        return False

    except AuthenticationError as e:
        console.print(f"\n[bold red]✗ Authentication Error:[/bold red] {e}")
        return False

    except KeyboardInterrupt:
        console.print("\n[yellow]✗ Interrupted by user[/yellow]")
        # TODO: Save checkpoint
        return False

    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected Error:[/bold red] {e}")

        # Show detailed error info if it's an APIError
        if hasattr(e, 'response_body') and e.response_body:
            console.print(f"\n[dim]API Response:[/dim]")
            console.print(f"[dim]{e.response_body[:500]}[/dim]")

        logger.exception("Scraping failed with exception")
        return False


def run_scrape(
    source: str = "all",
    projects: list[str] | None = None,
    spaces: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    dry_run: bool = False,
    resume: bool = False,
):
    """
    Run scraping operation (sync wrapper).

    Args:
        source: Source to scrape ("all", "jira", "confluence")
        projects: List of Jira project keys
        spaces: List of Confluence space keys
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        dry_run: Only count items, don't scrape
        resume: Resume from checkpoint
    """
    print_banner()

    success = asyncio.run(run_scrape_async(
        source=source,
        projects=projects,
        spaces=spaces,
        date_from=date_from,
        date_to=date_to,
        dry_run=dry_run,
        resume=resume,
    ))

    return 0 if success else 1


if __name__ == "__main__":
    # Setup logger
    setup_logger()

    # For now, run validation
    exit(run_validate())
