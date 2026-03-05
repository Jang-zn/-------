"""Data processing and statistics generation."""

from typing import List, Dict, Any
from datetime import datetime
from collections import defaultdict

from .logger import get_logger

logger = get_logger()


class DataProcessor:
    """Process and clean scraped data."""

    @staticmethod
    def process_jira_data(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process and clean Jira issue data.

        Args:
            issues: Raw issue data

        Returns:
            Processed issue data
        """
        processed = []

        for issue in issues:
            # Convert None to empty strings
            cleaned = {k: (v if v is not None else "") for k, v in issue.items()}
            processed.append(cleaned)

        logger.info(f"Processed {len(processed)} Jira issues")
        return processed

    @staticmethod
    def process_confluence_data(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process and clean Confluence page data.

        Args:
            pages: Raw page data

        Returns:
            Processed page data
        """
        processed = []

        for page in pages:
            # Convert None to empty strings
            cleaned = {k: (v if v is not None else "") for k, v in page.items()}
            processed.append(cleaned)

        logger.info(f"Processed {len(processed)} Confluence pages")
        return processed

    @staticmethod
    def generate_work_summary(
        issues: List[Dict[str, Any]],
        pages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate monthly/project work summary statistics.

        Args:
            issues: Processed Jira issues
            pages: Processed Confluence pages

        Returns:
            List of summary records by period and project
        """
        # Group issues by period (YYYY-MM) and project
        issue_groups = defaultdict(lambda: {
            "total_issues": 0,
            "completed_issues": 0,
            "story_points_total": 0.0,
            "bug_fixes": 0,
            "features": 0,
            "tasks": 0,
        })

        for issue in issues:
            created_date = issue.get("created_date", "")
            if not created_date:
                continue

            try:
                # Extract YYYY-MM
                period = created_date[:7]  # "2024-03-05" -> "2024-03"
            except Exception:
                continue

            project = issue.get("project_name", "Unknown")
            key = (period, project)

            # Update counts
            issue_groups[key]["total_issues"] += 1

            # Completed issues (status category = Done)
            status_category = issue.get("status_category", "")
            if status_category.lower() == "done":
                issue_groups[key]["completed_issues"] += 1

            # Story points
            story_points = issue.get("story_points", "")
            if story_points:
                try:
                    issue_groups[key]["story_points_total"] += float(story_points)
                except ValueError:
                    pass

            # Issue type counts
            issue_type = issue.get("issue_type", "").lower()
            if "bug" in issue_type:
                issue_groups[key]["bug_fixes"] += 1
            elif "story" in issue_type or "feature" in issue_type or "epic" in issue_type:
                issue_groups[key]["features"] += 1
            elif "task" in issue_type or "sub-task" in issue_type:
                issue_groups[key]["tasks"] += 1

        # Group pages by period and space
        page_groups = defaultdict(lambda: {"documents_authored": 0})

        for page in pages:
            created_date = page.get("created_date", "")
            if not created_date:
                continue

            try:
                period = created_date[:7]
            except Exception:
                continue

            space = page.get("space_name", "Unknown")
            key = (period, space)

            page_groups[key]["documents_authored"] += 1

        # Combine into summary records
        summary = []

        # Add issue summaries
        for (period, project), stats in issue_groups.items():
            summary.append({
                "period": period,
                "project": project,
                "total_issues": stats["total_issues"],
                "completed_issues": stats["completed_issues"],
                "story_points_total": round(stats["story_points_total"], 1),
                "bug_fixes": stats["bug_fixes"],
                "features": stats["features"],
                "tasks": stats["tasks"],
                "documents_authored": 0,
                "total_time_spent_hours": 0,  # Would need time tracking data
            })

        # Add page summaries
        for (period, space), stats in page_groups.items():
            # Check if we already have an entry for this period/project
            existing = None
            for record in summary:
                if record["period"] == period and record["project"] == space:
                    existing = record
                    break

            if existing:
                existing["documents_authored"] = stats["documents_authored"]
            else:
                summary.append({
                    "period": period,
                    "project": space,
                    "total_issues": 0,
                    "completed_issues": 0,
                    "story_points_total": 0.0,
                    "bug_fixes": 0,
                    "features": 0,
                    "tasks": 0,
                    "documents_authored": stats["documents_authored"],
                    "total_time_spent_hours": 0,
                })

        # Sort by period descending
        summary.sort(key=lambda x: x["period"], reverse=True)

        logger.info(f"Generated {len(summary)} summary records")
        return summary
