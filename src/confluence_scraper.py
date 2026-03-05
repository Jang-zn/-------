"""Confluence scraper for collecting pages and related data."""

from typing import Dict, List, Any
from bs4 import BeautifulSoup

from .http_client import AtlassianClient
from .config import ConfluenceConfig, UserConfig
from .logger import get_logger
from .utils import safe_get, parse_datetime, html_to_text, join_list, truncate_text

logger = get_logger()


class CQLBuilder:
    """Build CQL queries for filtering Confluence pages."""

    def __init__(self, user_config: UserConfig, confluence_config: ConfluenceConfig):
        """
        Initialize CQL builder.

        Args:
            user_config: User configuration
            confluence_config: Confluence configuration
        """
        self.user_config = user_config
        self.confluence_config = confluence_config

    def build_query(self) -> str:
        """
        Build CQL query to fetch user's pages.

        Returns:
            CQL query string
        """
        conditions = []

        # User's pages (creator)
        # Use currentUser() instead of account ID for better compatibility
        conditions.append("creator = currentUser()")

        # Only pages (not blog posts)
        conditions.append("type = page")

        # Space filter
        if self.confluence_config.spaces:
            spaces_str = " OR ".join([f'space = "{s}"' for s in self.confluence_config.spaces])
            conditions.append(f"({spaces_str})")

        # Date filter
        if self.confluence_config.date_from:
            conditions.append(f'created >= "{self.confluence_config.date_from}"')

        if self.confluence_config.date_to:
            conditions.append(f'created <= "{self.confluence_config.date_to}"')

        # Combine conditions
        cql = " AND ".join(conditions)

        # Order by created date descending
        cql += " ORDER BY created DESC"

        logger.debug(f"Built CQL query: {cql}")
        return cql


class ConfluenceScraper:
    """Scraper for Confluence pages."""

    def __init__(
        self,
        client: AtlassianClient,
        user_config: UserConfig,
        confluence_config: ConfluenceConfig,
    ):
        """
        Initialize Confluence scraper.

        Args:
            client: HTTP client for Confluence API
            user_config: User configuration
            confluence_config: Confluence configuration
        """
        self.client = client
        self.user_config = user_config
        self.confluence_config = confluence_config
        self.cql_builder = CQLBuilder(user_config, confluence_config)

    async def count_pages(self) -> int:
        """
        Count total pages matching the query.

        Returns:
            Total page count
        """
        cql = self.cql_builder.build_query()

        response = await self.client.get(
            "/rest/api/content/search",
            params={
                "cql": cql,
                "limit": 0,  # Only get count
            }
        )

        data = response.json()
        total = data.get("totalSize", 0)

        logger.info(f"Found {total} pages matching query")
        return total

    async def scrape_all(self) -> List[Dict[str, Any]]:
        """
        Scrape all pages matching the query.

        Returns:
            List of processed page dictionaries
        """
        cql = self.cql_builder.build_query()
        pages = []

        logger.info("Starting Confluence page collection...")

        # First, get page IDs from search
        page_ids = []
        try:
            async for result in self.client.paginate_confluence(
                "/rest/api/content/search",
                params={"cql": cql}
            ):
                page_id = result.get("id")
                if page_id:
                    page_ids.append(page_id)

                # Safety check to prevent infinite loops
                if len(page_ids) > 10000:
                    logger.warning("Reached 10,000 pages limit, stopping pagination")
                    break
        except Exception as e:
            logger.error(f"Error during pagination: {e}")
            if not page_ids:
                raise

        logger.info(f"Found {len(page_ids)} pages, fetching details...")

        # Then fetch full details for each page
        for i, page_id in enumerate(page_ids, 1):
            try:
                processed = await self._fetch_and_process_page(page_id)
                pages.append(processed)

                if i % 10 == 0:
                    logger.info(f"Collected {i}/{len(page_ids)} pages...")

            except Exception as e:
                logger.warning(f"Failed to process page {page_id}: {e}")
                continue

        logger.info(f"✓ Collected {len(pages)} pages total")
        return pages

    async def _fetch_and_process_page(self, page_id: str) -> Dict[str, Any]:
        """
        Fetch full page details and process.

        Args:
            page_id: Page ID

        Returns:
            Processed page dictionary with 17 fields
        """
        # Fetch page with all expansions
        response = await self.client.get(
            f"/rest/api/content/{page_id}",
            params={
                "expand": "body.storage,history,version,ancestors,metadata.labels,space"
            }
        )

        page = response.json()
        return self._process_page(page)

    def _process_page(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single page and extract all fields.

        Args:
            page: Raw page data from API

        Returns:
            Processed page dictionary with 17 fields
        """
        page_id = page.get("id", "")
        space = page.get("space", {})
        history = page.get("history", {})
        version = page.get("version", {})
        body = page.get("body", {})
        metadata = page.get("metadata", {})
        ancestors = page.get("ancestors", [])

        # Extract content
        content_plain, content_summary, content_length = self._extract_content(body)

        # Extract labels
        labels_data = metadata.get("labels", {}).get("results", [])
        labels = [label.get("name", "") for label in labels_data]

        # Get parent page
        parent_title = ""
        if ancestors:
            parent_title = ancestors[-1].get("title", "")

        # Get URL
        base_url = safe_get(page, "_links", "base", default=self.client.base_url)
        web_ui = safe_get(page, "_links", "webui", default="")
        url = f"{base_url}{web_ui}" if web_ui else ""

        # Creator and modifier
        creator = safe_get(history, "createdBy", "displayName", default="")
        last_modifier = safe_get(version, "by", "displayName", default="")

        # Build result
        result = {
            "page_id": page_id,
            "space_key": space.get("key", ""),
            "space_name": space.get("name", ""),
            "title": page.get("title", ""),
            "content_type": page.get("type", ""),
            "content_plain": content_plain,
            "content_summary": content_summary,
            "content_length": content_length,
            "author": creator,
            "created_date": parse_datetime(history.get("createdDate")),
            "last_modified_date": parse_datetime(version.get("when")),
            "last_modifier": last_modifier,
            "version_count": version.get("number", 0),
            "labels": join_list(labels),
            "parent_page_title": parent_title,
            "comments_count": 0,  # Would need separate API call
            "url": url,
        }

        return result

    def _extract_content(self, body: Dict[str, Any]) -> tuple[str, str, int]:
        """
        Extract and convert page content to plain text.

        Args:
            body: Page body data

        Returns:
            Tuple of (content_plain, content_summary, content_length)
        """
        if not self.confluence_config.include_content:
            return "", "", 0

        # Get storage format (HTML with Confluence macros)
        storage = body.get("storage", {})
        html_content = storage.get("value", "")

        if not html_content:
            return "", "", 0

        # Parse HTML and remove Confluence macros
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Remove Confluence-specific elements
            # ac:structured-macro tags (Confluence macros)
            for macro in soup.find_all("ac:structured-macro"):
                # Keep plain text content if it exists
                plain_text = macro.find("ac:plain-text-body")
                if plain_text:
                    macro.replace_with(plain_text.get_text())
                else:
                    macro.decompose()

            # Remove other Confluence-specific tags
            for tag_name in ["ac:link", "ac:image", "ri:attachment", "ri:page"]:
                for tag in soup.find_all(tag_name):
                    tag.decompose()

            # Get plain text
            text = soup.get_text(separator=" ", strip=True)
            text = " ".join(text.split())  # Normalize whitespace

            content_length = len(text)
            content_plain = truncate_text(text, max_length=2000)
            content_summary = truncate_text(text, max_length=200)

            return content_plain, content_summary, content_length

        except Exception as e:
            logger.warning(f"Failed to parse page content: {e}")
            # Return raw HTML as fallback
            text = html_to_text(html_content, max_length=2000)
            return text, truncate_text(text, 200), len(text)
