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
        if config.jira.enabled:
            console.print("\n[cyan]Testing Jira connection...[/cyan]")
            jira_client = AtlassianClient(
                base_url=config.server.jira_base_url,
                auth=auth,
                config=config.execution,
            )
            try:
                await auth.validate_jira_connection(jira_client)
            finally:
                await jira_client.close()

        # Test Confluence connection
        if config.confluence.enabled:
            console.print("\n[cyan]Testing Confluence connection...[/cyan]")
            confluence_client = AtlassianClient(
                base_url=config.server.confluence_base_url,
                auth=auth,
                config=config.execution,
            )
            try:
                await auth.validate_confluence_connection(confluence_client)
            finally:
                await confluence_client.close()

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
    Run scraping operation.

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

    console.print("[yellow]Scraping functionality coming soon...[/yellow]")
    console.print(f"Source: {source}")
    console.print(f"Dry run: {dry_run}")
    console.print(f"Resume: {resume}")

    # TODO: Implement scraping logic in next phases
    return 0


if __name__ == "__main__":
    # Setup logger
    setup_logger()

    # For now, run validation
    exit(run_validate())
