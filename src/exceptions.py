"""Custom exception classes for the scraper."""


class ScraperError(Exception):
    """Base exception for all scraper errors."""

    pass


class ConfigValidationError(ScraperError):
    """Raised when configuration validation fails."""

    pass


class AuthenticationError(ScraperError):
    """Raised when authentication fails."""

    pass


class RateLimitError(ScraperError):
    """Raised when API rate limit is exceeded."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class APIError(ScraperError):
    """Raised when API request fails."""

    def __init__(self, message: str, status_code: int | None = None, response_body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
