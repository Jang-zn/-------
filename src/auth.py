"""Authentication module for Atlassian Cloud APIs."""

import base64
from typing import Dict

from .config import EnvConfig, ServerConfig
from .exceptions import AuthenticationError
from .logger import get_logger, mask_token

logger = get_logger()


class AtlassianAuth:
    """Handles authentication for Atlassian Cloud APIs."""

    def __init__(self, env_config: EnvConfig):
        """
        Initialize authentication.

        Args:
            env_config: Environment configuration with email and API token
        """
        self.email = env_config.atlassian_email
        self.api_token = env_config.atlassian_api_token

        logger.debug(f"Initialized auth for email: {self.email}")
        logger.debug(f"API token: {mask_token(self.api_token)}")

    def get_auth_headers(self) -> Dict[str, str]:
        """
        Generate HTTP Basic Auth headers for Atlassian Cloud.

        Returns:
            Dictionary with Authorization header

        Example:
            Authorization: Basic base64(email:api_token)
        """
        # Combine email and token
        credentials = f"{self.email}:{self.api_token}"

        # Encode to base64
        encoded = base64.b64encode(credentials.encode()).decode()

        return {
            "Authorization": f"Basic {encoded}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def validate_jira_connection(self, http_client) -> dict:
        """
        Validate Jira API connection.

        Args:
            http_client: HTTP client instance

        Returns:
            User information dict from /rest/api/2/myself

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            response = await http_client.get("/rest/api/2/myself")
            user_data = response.json()

            logger.info(f"✓ Jira connection validated for user: {user_data.get('displayName')}")
            logger.debug(f"Account ID: {user_data.get('accountId')}")

            return user_data

        except Exception as e:
            logger.error(f"✗ Jira authentication failed: {e}")
            raise AuthenticationError(
                "Failed to authenticate with Jira API. "
                "Please check your email and API token in .env file."
            )

    async def validate_confluence_connection(self, http_client) -> dict:
        """
        Validate Confluence API connection.

        Args:
            http_client: HTTP client instance

        Returns:
            User information dict from /rest/api/user/current

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            response = await http_client.get("/rest/api/user/current")
            user_data = response.json()

            logger.info(f"✓ Confluence connection validated for user: {user_data.get('displayName')}")
            logger.debug(f"Account ID: {user_data.get('accountId')}")

            return user_data

        except Exception as e:
            logger.error(f"✗ Confluence authentication failed: {e}")
            raise AuthenticationError(
                "Failed to authenticate with Confluence API. "
                "Please check your email and API token in .env file."
            )
