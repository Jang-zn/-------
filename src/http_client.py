"""HTTP client for Atlassian APIs with retry and rate limiting."""

import asyncio
import time
from typing import AsyncIterator, Dict, Any

import httpx

from .auth import AtlassianAuth
from .config import ExecutionConfig
from .exceptions import APIError, RateLimitError
from .logger import get_logger

logger = get_logger()


class AtlassianClient:
    """HTTP client for Atlassian Cloud APIs."""

    def __init__(
        self,
        base_url: str,
        auth: AtlassianAuth,
        config: ExecutionConfig,
    ):
        """
        Initialize HTTP client.

        Args:
            base_url: Base URL for the API
            auth: Authentication handler
            config: Execution configuration
        """
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.config = config

        # Rate limiting
        self.rate_limit_delay = 1.0 / config.rate_limit_per_second
        self.last_request_time = 0.0

        # HTTP client
        self.client = httpx.AsyncClient(
            timeout=config.timeout_seconds,
            headers=auth.get_auth_headers(),
        )

        logger.debug(f"Initialized HTTP client for {base_url}")
        logger.debug(f"Rate limit: {config.rate_limit_per_second} req/s")

    async def _wait_for_rate_limit(self):
        """Implement simple rate limiting with sleep."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - time_since_last_request
            await asyncio.sleep(wait_time)

        self.last_request_time = time.time()

    async def get(self, endpoint: str, params: Dict[str, Any] | None = None) -> httpx.Response:
        """
        Make GET request with retry logic.

        Args:
            endpoint: API endpoint (e.g., "/rest/api/2/search")
            params: Query parameters

        Returns:
            HTTP response

        Raises:
            APIError: If request fails after retries
            RateLimitError: If rate limit exceeded
        """
        url = f"{self.base_url}{endpoint}"

        for attempt in range(1, self.config.max_retries + 1):
            try:
                # Apply rate limiting
                await self._wait_for_rate_limit()

                # Make request
                response = await self.client.get(url, params=params)

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limit hit. Waiting {retry_after}s...")

                    if attempt < self.config.max_retries:
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        raise RateLimitError(
                            f"Rate limit exceeded after {self.config.max_retries} retries",
                            retry_after=retry_after
                        )

                # Handle authentication errors
                if response.status_code in (401, 403):
                    raise APIError(
                        f"Authentication failed: {response.status_code}",
                        status_code=response.status_code,
                        response_body=response.text
                    )

                # Handle server errors with retry
                if response.status_code >= 500:
                    logger.warning(
                        f"Server error {response.status_code} on attempt {attempt}/{self.config.max_retries}"
                    )

                    if attempt < self.config.max_retries:
                        # Exponential backoff
                        wait_time = 2 ** attempt
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise APIError(
                            f"Server error after {self.config.max_retries} retries",
                            status_code=response.status_code,
                            response_body=response.text
                        )

                # Handle client errors (4xx except 401, 403, 429)
                if 400 <= response.status_code < 500:
                    raise APIError(
                        f"Client error: {response.status_code}",
                        status_code=response.status_code,
                        response_body=response.text
                    )

                # Success
                response.raise_for_status()
                return response

            except httpx.TimeoutException:
                logger.warning(f"Request timeout on attempt {attempt}/{self.config.max_retries}")

                if attempt < self.config.max_retries:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise APIError(f"Request timeout after {self.config.max_retries} retries")

            except (RateLimitError, APIError):
                # Re-raise our custom exceptions
                raise

            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt}: {e}")

                if attempt < self.config.max_retries:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise APIError(f"Request failed after {self.config.max_retries} retries: {e}")

        # Should never reach here
        raise APIError("Request failed for unknown reason")

    async def paginate_jira(
        self,
        endpoint: str,
        params: Dict[str, Any] | None = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Paginate through Jira API results.

        Jira API v3 uses cursor-based pagination with nextPageToken.

        Args:
            endpoint: API endpoint
            params: Base query parameters

        Yields:
            Individual items from results
        """
        if params is None:
            params = {}

        params["maxResults"] = self.config.page_size
        next_page_token = None
        page_count = 0

        while True:
            # Add nextPageToken if available
            if next_page_token:
                params["nextPageToken"] = next_page_token
            elif "nextPageToken" in params:
                del params["nextPageToken"]

            response = await self.get(endpoint, params=params)
            data = response.json()

            # Get items (could be "issues", "values", etc.)
            items = data.get("issues") or data.get("values") or []

            if not items:
                break

            page_count += 1
            for item in items:
                yield item

            # Check if there are more results (API v3 cursor-based pagination)
            is_last = data.get("isLast", True)
            next_page_token = data.get("nextPageToken")

            if is_last or not next_page_token:
                break

            logger.debug(f"Pagination: page {page_count}, continuing...")

    async def paginate_confluence(
        self,
        endpoint: str,
        params: Dict[str, Any] | None = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Paginate through Confluence API results.

        Confluence uses start/limit pagination.

        Args:
            endpoint: API endpoint
            params: Base query parameters

        Yields:
            Individual items from results
        """
        if params is None:
            params = {}

        start = 0
        params["limit"] = self.config.page_size

        while True:
            params["start"] = start

            response = await self.get(endpoint, params=params)
            data = response.json()

            # Get items from results
            results = data.get("results", [])

            if not results:
                break

            for item in results:
                yield item

            # Check if there are more results
            size = data.get("size", 0)
            start += size

            # Confluence doesn't always provide total, check if we got less than requested
            if size < self.config.page_size:
                break

            logger.debug(f"Pagination: {start}+ items")

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
        logger.debug("HTTP client closed")
