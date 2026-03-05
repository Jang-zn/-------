"""Jira scraper for collecting issues and related data."""

from typing import Dict, List, Any, Optional
from datetime import datetime

from .http_client import AtlassianClient
from .config import JiraConfig, UserConfig
from .logger import get_logger
from .utils import safe_get, parse_datetime, adf_to_text, html_to_text, join_list, truncate_text

logger = get_logger()


class JQLBuilder:
    """Build JQL queries for filtering Jira issues."""

    def __init__(self, user_config: UserConfig, jira_config: JiraConfig):
        """
        Initialize JQL builder.

        Args:
            user_config: User configuration
            jira_config: Jira configuration
        """
        self.user_config = user_config
        self.jira_config = jira_config

    def build_query(self) -> str:
        """
        Build JQL query to fetch user's issues.

        Returns:
            JQL query string
        """
        conditions = []

        # User's issues (assignee OR reporter)
        account_id = self.user_config.account_id
        conditions.append(f"(assignee = {account_id} OR reporter = {account_id})")

        # Project filter
        if self.jira_config.projects:
            projects_str = ", ".join([f'"{p}"' for p in self.jira_config.projects])
            conditions.append(f"project IN ({projects_str})")

        # Date filter
        if self.jira_config.date_from:
            conditions.append(f'created >= "{self.jira_config.date_from}"')

        if self.jira_config.date_to:
            conditions.append(f'created <= "{self.jira_config.date_to}"')

        # Combine conditions
        jql = " AND ".join(conditions)

        # Order by created date descending
        jql += " ORDER BY created DESC"

        logger.debug(f"Built JQL query: {jql}")
        return jql


class JiraScraper:
    """Scraper for Jira issues."""

    def __init__(
        self,
        client: AtlassianClient,
        user_config: UserConfig,
        jira_config: JiraConfig,
    ):
        """
        Initialize Jira scraper.

        Args:
            client: HTTP client for Jira API
            user_config: User configuration
            jira_config: Jira configuration
        """
        self.client = client
        self.user_config = user_config
        self.jira_config = jira_config
        self.jql_builder = JQLBuilder(user_config, jira_config)

    async def count_issues(self) -> int | None:
        """
        Count total issues matching the query.

        Note: Jira API v3 uses cursor-based pagination and doesn't provide
        a total count upfront. We return None to indicate unknown count.

        Returns:
            None (total count not available in API v3)
        """
        logger.info("Jira API v3 doesn't provide total count, will paginate until exhausted")
        return None

    async def scrape_all(self) -> List[Dict[str, Any]]:
        """
        Scrape all issues matching the query.

        Returns:
            List of processed issue dictionaries
        """
        jql = self.jql_builder.build_query()
        issues = []

        logger.info("Starting Jira issue collection...")

        # Paginate through all issues
        async for issue in self.client.paginate_jira(
            "/rest/api/3/search/jql",
            params={
                "jql": jql,
                "fields": "*all",  # Get all fields including custom fields
                "expand": "renderedFields",
            }
        ):
            try:
                processed = await self._process_issue(issue)
                issues.append(processed)

                if len(issues) % 50 == 0:
                    logger.info(f"Collected {len(issues)} issues...")

            except Exception as e:
                issue_key = safe_get(issue, "key", default="UNKNOWN")
                logger.warning(f"Failed to process issue {issue_key}: {e}")
                continue

        logger.info(f"✓ Collected {len(issues)} issues total")
        return issues

    async def _process_issue(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single issue and extract all fields.

        Args:
            issue: Raw issue data from API

        Returns:
            Processed issue dictionary with 30 fields
        """
        fields = issue.get("fields", {})
        key = issue.get("key", "")

        # Basic fields
        project = fields.get("project", {})
        issue_type = fields.get("issuetype", {})
        status = fields.get("status", {})
        priority = fields.get("priority", {})
        assignee = fields.get("assignee", {})
        reporter = fields.get("reporter", {})
        resolution = fields.get("resolution", {})
        parent = fields.get("parent", {})

        # Extract description
        description = self._extract_description(fields)

        # Extract components and labels
        components = [c.get("name", "") for c in fields.get("components", [])]
        labels = fields.get("labels", [])
        fix_versions = [v.get("name", "") for v in fields.get("fixVersions", [])]

        # Epic information
        epic_key, epic_name = await self._extract_epic_info(fields)

        # Sprint information
        sprint_name = self._extract_sprint_info(fields)

        # Story points (common custom field names)
        story_points = self._extract_story_points(fields)

        # Linked issues
        linked_issues_count = len(fields.get("issuelinks", []))

        # Comments
        comments_data = await self._extract_comments(key) if self.jira_config.include_comments else {}

        # Build result
        result = {
            # Basic fields (20)
            "issue_key": key,
            "project_key": project.get("key", ""),
            "project_name": project.get("name", ""),
            "issue_type": issue_type.get("name", ""),
            "summary": fields.get("summary", ""),
            "description": description,
            "status": status.get("name", ""),
            "status_category": safe_get(status, "statusCategory", "name", default=""),
            "priority": priority.get("name", "") if priority else "",
            "assignee": assignee.get("displayName", "") if assignee else "",
            "reporter": reporter.get("displayName", "") if reporter else "",
            "created_date": parse_datetime(fields.get("created")),
            "updated_date": parse_datetime(fields.get("updated")),
            "resolved_date": parse_datetime(fields.get("resolutiondate")),
            "resolution": resolution.get("name", "") if resolution else "",
            "components": join_list(components),
            "labels": join_list(labels),
            "fix_versions": join_list(fix_versions),
            "parent_key": parent.get("key", "") if parent else "",
            "url": f"{self.client.base_url}/browse/{key}",

            # Epic/Sprint fields (5)
            "epic_key": epic_key,
            "epic_name": epic_name,
            "sprint_name": sprint_name,
            "story_points": story_points,
            "linked_issues_count": linked_issues_count,

            # Comment fields (5)
            "comments_count": comments_data.get("total", 0),
            "my_comments_count": comments_data.get("my_count", 0),
            "my_latest_comment": comments_data.get("latest", ""),
            "my_comments_summary": comments_data.get("summary", ""),
            "parent_summary": safe_get(parent, "fields", "summary", default="") if parent else "",
        }

        return result

    def _extract_description(self, fields: Dict[str, Any]) -> str:
        """
        Extract and convert description to plain text.

        Args:
            fields: Issue fields

        Returns:
            Plain text description (max 1000 chars)
        """
        # Try ADF format first (newer Jira)
        description = fields.get("description")

        if isinstance(description, dict):
            # ADF format
            text = adf_to_text(description, max_length=1000)
            if text:
                return text

        # Try HTML format (older Jira or rendered fields)
        if isinstance(description, str):
            return html_to_text(description, max_length=1000)

        return ""

    async def _extract_epic_info(self, fields: Dict[str, Any]) -> tuple[str, str]:
        """
        Extract epic key and name.

        Args:
            fields: Issue fields

        Returns:
            Tuple of (epic_key, epic_name)
        """
        epic_key = ""
        epic_name = ""

        # Try parent field first (for subtasks/stories under epic)
        parent = fields.get("parent", {})
        if parent:
            parent_type = safe_get(parent, "fields", "issuetype", "name", default="")
            if parent_type == "Epic":
                epic_key = parent.get("key", "")
                epic_name = safe_get(parent, "fields", "summary", default="")
                return epic_key, epic_name

        # Try common custom field names for epic link
        # These vary by organization, check multiple possibilities
        epic_link_fields = [
            "customfield_10014",  # Common default
            "customfield_10008",
            "customfield_10100",
        ]

        for field_name in epic_link_fields:
            epic_key = fields.get(field_name)
            if epic_key:
                break

        # If we found epic key, fetch epic name if configured
        if epic_key and self.jira_config.resolve_epics:
            try:
                epic_name = await self._fetch_epic_name(epic_key)
            except Exception as e:
                logger.warning(f"Failed to fetch epic name for {epic_key}: {e}")

        return epic_key or "", epic_name

    async def _fetch_epic_name(self, epic_key: str) -> str:
        """
        Fetch epic name from API.

        Args:
            epic_key: Epic issue key

        Returns:
            Epic name/summary
        """
        try:
            response = await self.client.get(f"/rest/api/3/issue/{epic_key}")
            data = response.json()
            return safe_get(data, "fields", "summary", default="")
        except Exception as e:
            logger.debug(f"Could not fetch epic {epic_key}: {e}")
            return ""

    def _extract_sprint_info(self, fields: Dict[str, Any]) -> str:
        """
        Extract sprint information.

        Args:
            fields: Issue fields

        Returns:
            Sprint name or empty string
        """
        if not self.jira_config.resolve_sprints:
            return ""

        # Common sprint custom field names
        sprint_fields = [
            "customfield_10020",  # Common default
            "customfield_10010",
            "customfield_10104",
        ]

        for field_name in sprint_fields:
            sprint_data = fields.get(field_name)

            if sprint_data:
                # Sprint data can be an array or single object
                if isinstance(sprint_data, list) and sprint_data:
                    sprint_data = sprint_data[-1]  # Get latest sprint

                # Sprint data might be a string or dict
                if isinstance(sprint_data, dict):
                    return sprint_data.get("name", "")
                elif isinstance(sprint_data, str):
                    # Parse sprint string format
                    # Example: "com.atlassian.greenhopper.service.sprint.Sprint@14b7a[id=123,name=Sprint 1]"
                    if "name=" in sprint_data:
                        try:
                            name_part = sprint_data.split("name=")[1]
                            name = name_part.split(",")[0].split("]")[0]
                            return name
                        except Exception:
                            pass

        return ""

    def _extract_story_points(self, fields: Dict[str, Any]) -> str:
        """
        Extract story points.

        Args:
            fields: Issue fields

        Returns:
            Story points as string or empty string
        """
        # Common story point custom field names
        story_point_fields = [
            "customfield_10016",  # Common default
            "customfield_10026",
            "customfield_10106",
        ]

        for field_name in story_point_fields:
            points = fields.get(field_name)
            if points is not None:
                return str(points)

        return ""

    async def _extract_comments(self, issue_key: str) -> Dict[str, Any]:
        """
        Extract comment information for the issue.

        Args:
            issue_key: Issue key

        Returns:
            Dictionary with comment data
        """
        try:
            response = await self.client.get(f"/rest/api/3/issue/{issue_key}/comment")
            data = response.json()

            comments = data.get("comments", [])
            total_count = len(comments)

            # Filter for user's comments
            my_comments = [
                c for c in comments
                if safe_get(c, "author", "accountId") == self.user_config.account_id
            ]

            my_count = len(my_comments)

            # Get latest comment
            latest = ""
            if my_comments:
                latest_comment = my_comments[-1]  # Last comment
                body = latest_comment.get("body", "")

                # Convert to text
                if isinstance(body, dict):
                    latest = adf_to_text(body, max_length=500)
                elif isinstance(body, str):
                    latest = html_to_text(body, max_length=500)

            # Create summary of all my comments
            summary_parts = []
            for comment in my_comments[:5]:  # Max 5 comments
                body = comment.get("body", "")

                if isinstance(body, dict):
                    text = adf_to_text(body, max_length=200)
                elif isinstance(body, str):
                    text = html_to_text(body, max_length=200)
                else:
                    text = ""

                if text:
                    summary_parts.append(text)

            summary = " | ".join(summary_parts)
            summary = truncate_text(summary, max_length=1000)

            return {
                "total": total_count,
                "my_count": my_count,
                "latest": latest,
                "summary": summary,
            }

        except Exception as e:
            logger.warning(f"Failed to fetch comments for {issue_key}: {e}")
            return {
                "total": 0,
                "my_count": 0,
                "latest": "",
                "summary": "",
            }
