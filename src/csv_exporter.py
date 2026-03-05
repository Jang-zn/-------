"""CSV export functionality using pandas."""

import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

import pandas as pd

from .config import OutputConfig
from .logger import get_logger

logger = get_logger()


class CSVExporter:
    """Export data to CSV files."""

    # Define column order for Jira issues (30 columns)
    JIRA_COLUMNS = [
        "issue_key",
        "project_key",
        "project_name",
        "issue_type",
        "summary",
        "description",
        "status",
        "status_category",
        "priority",
        "assignee",
        "reporter",
        "created_date",
        "updated_date",
        "resolved_date",
        "resolution",
        "components",
        "labels",
        "fix_versions",
        "parent_key",
        "parent_summary",
        "epic_key",
        "epic_name",
        "sprint_name",
        "story_points",
        "linked_issues_count",
        "comments_count",
        "my_comments_count",
        "my_latest_comment",
        "my_comments_summary",
        "url",
    ]

    # Define column order for Confluence pages (17 columns)
    CONFLUENCE_COLUMNS = [
        "page_id",
        "space_key",
        "space_name",
        "title",
        "content_type",
        "content_plain",
        "content_summary",
        "content_length",
        "author",
        "created_date",
        "last_modified_date",
        "last_modifier",
        "version_count",
        "labels",
        "parent_page_title",
        "comments_count",
        "url",
    ]

    # Define column order for work summary (10 columns)
    SUMMARY_COLUMNS = [
        "period",
        "project",
        "total_issues",
        "completed_issues",
        "story_points_total",
        "bug_fixes",
        "features",
        "tasks",
        "documents_authored",
        "total_time_spent_hours",
    ]

    def __init__(self, output_config: OutputConfig):
        """
        Initialize CSV exporter.

        Args:
            output_config: Output configuration
        """
        self.config = output_config

        # Create output directory
        self.output_dir = Path(output_config.directory)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(f"CSV exporter initialized, output dir: {self.output_dir}")

    def export_jira(self, issues: List[Dict[str, Any]]) -> Path:
        """
        Export Jira issues to CSV.

        Args:
            issues: List of processed issue dictionaries

        Returns:
            Path to generated CSV file
        """
        if not issues:
            logger.warning("No Jira issues to export")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"work_history_jira_issues_{timestamp}.csv"
        filepath = self.output_dir / filename

        # Create DataFrame with defined column order
        df = pd.DataFrame(issues)

        # Ensure all columns exist (add missing with empty values)
        for col in self.JIRA_COLUMNS:
            if col not in df.columns:
                df[col] = ""

        # Reorder columns
        df = df[self.JIRA_COLUMNS]

        # Export to CSV
        df.to_csv(
            filepath,
            index=False,
            encoding=self.config.encoding,
            quoting=csv.QUOTE_ALL,  # Quote all fields for safety
        )

        logger.info(f"✓ Exported {len(issues)} Jira issues to {filename}")
        return filepath

    def export_confluence(self, pages: List[Dict[str, Any]]) -> Path:
        """
        Export Confluence pages to CSV.

        Args:
            pages: List of processed page dictionaries

        Returns:
            Path to generated CSV file
        """
        if not pages:
            logger.warning("No Confluence pages to export")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"work_history_confluence_pages_{timestamp}.csv"
        filepath = self.output_dir / filename

        # Create DataFrame with defined column order
        df = pd.DataFrame(pages)

        # Ensure all columns exist
        for col in self.CONFLUENCE_COLUMNS:
            if col not in df.columns:
                df[col] = ""

        # Reorder columns
        df = df[self.CONFLUENCE_COLUMNS]

        # Export to CSV
        df.to_csv(
            filepath,
            index=False,
            encoding=self.config.encoding,
            quoting=csv.QUOTE_ALL,
        )

        logger.info(f"✓ Exported {len(pages)} Confluence pages to {filename}")
        return filepath

    def export_summary(self, summary: List[Dict[str, Any]]) -> Path:
        """
        Export work summary statistics to CSV.

        Args:
            summary: List of summary records

        Returns:
            Path to generated CSV file
        """
        if not summary:
            logger.warning("No summary data to export")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"work_history_work_summary_{timestamp}.csv"
        filepath = self.output_dir / filename

        # Create DataFrame with defined column order
        df = pd.DataFrame(summary)

        # Ensure all columns exist
        for col in self.SUMMARY_COLUMNS:
            if col not in df.columns:
                df[col] = 0 if col != "project" and col != "period" else ""

        # Reorder columns
        df = df[self.SUMMARY_COLUMNS]

        # Export to CSV
        df.to_csv(
            filepath,
            index=False,
            encoding=self.config.encoding,
            quoting=csv.QUOTE_ALL,
        )

        logger.info(f"✓ Exported {len(summary)} summary records to {filename}")
        return filepath
