"""Configuration management using Pydantic models and YAML."""

from pathlib import Path
from typing import Literal
from datetime import datetime

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings

from .exceptions import ConfigValidationError


class ServerConfig(BaseModel):
    """Server configuration for Jira and Confluence."""

    type: Literal["cloud"] = Field(default="cloud", description="Server type (cloud or server)")
    jira_base_url: str = Field(..., description="Jira base URL")
    confluence_base_url: str = Field(..., description="Confluence base URL")

    @field_validator("jira_base_url", "confluence_base_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure URLs don't end with trailing slash."""
        return v.rstrip("/")


class UserConfig(BaseModel):
    """User configuration."""

    account_id: str = Field(..., description="Atlassian account ID")
    display_name: str = Field(..., description="User display name")


class JiraConfig(BaseModel):
    """Jira scraping configuration."""

    enabled: bool = Field(default=True, description="Enable Jira scraping")
    projects: list[str] = Field(default_factory=list, description="Project keys to scrape (empty = all)")
    date_from: str | None = Field(default=None, description="Start date (YYYY-MM-DD)")
    date_to: str | None = Field(default=None, description="End date (YYYY-MM-DD)")
    include_comments: bool = Field(default=True, description="Include comment data")
    resolve_epics: bool = Field(default=True, description="Resolve epic names")
    resolve_sprints: bool = Field(default=True, description="Resolve sprint information")

    @field_validator("date_from", "date_to")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        """Validate date format."""
        if v:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"Invalid date format: {v}. Expected YYYY-MM-DD")
        return v


class ConfluenceConfig(BaseModel):
    """Confluence scraping configuration."""

    enabled: bool = Field(default=True, description="Enable Confluence scraping")
    spaces: list[str] = Field(default_factory=list, description="Space keys to scrape (empty = all)")
    date_from: str | None = Field(default=None, description="Start date (YYYY-MM-DD)")
    date_to: str | None = Field(default=None, description="End date (YYYY-MM-DD)")
    include_content: bool = Field(default=True, description="Include page content")

    @field_validator("date_from", "date_to")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        """Validate date format."""
        if v:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"Invalid date format: {v}. Expected YYYY-MM-DD")
        return v


class OutputConfig(BaseModel):
    """Output configuration."""

    directory: str = Field(default="./output", description="Output directory path")
    encoding: str = Field(default="utf-8-sig", description="CSV file encoding")
    date_format: str = Field(default="%Y-%m-%d", description="Date format in CSV")


class ExecutionConfig(BaseModel):
    """Execution configuration."""

    rate_limit_per_second: int = Field(default=3, ge=1, le=10, description="API requests per second")
    page_size: int = Field(default=50, ge=10, le=100, description="Items per page")
    max_retries: int = Field(default=3, ge=1, le=10, description="Maximum retry attempts")
    timeout_seconds: int = Field(default=30, ge=5, le=300, description="Request timeout in seconds")
    log_level: str = Field(default="INFO", description="Logging level")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper


class AppConfig(BaseModel):
    """Main application configuration."""

    server: ServerConfig
    user: UserConfig
    jira: JiraConfig = Field(default_factory=JiraConfig)
    confluence: ConfluenceConfig = Field(default_factory=ConfluenceConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)


class EnvConfig(BaseSettings):
    """Environment variables configuration."""

    atlassian_email: str = Field(..., alias="ATLASSIAN_EMAIL")
    atlassian_api_token: str = Field(..., alias="ATLASSIAN_API_TOKEN")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def load_config(config_path: str | Path = "config/config.yaml") -> AppConfig:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to configuration YAML file

    Returns:
        Validated AppConfig instance

    Raises:
        ConfigValidationError: If configuration is invalid
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise ConfigValidationError(f"Configuration file not found: {config_file}")

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        if not config_data:
            raise ConfigValidationError("Configuration file is empty")

        return AppConfig(**config_data)

    except yaml.YAMLError as e:
        raise ConfigValidationError(f"Failed to parse YAML: {e}")
    except Exception as e:
        raise ConfigValidationError(f"Configuration validation failed: {e}")


def load_env_config() -> EnvConfig:
    """
    Load environment variables.

    Returns:
        Validated EnvConfig instance

    Raises:
        ConfigValidationError: If environment variables are missing or invalid
    """
    try:
        return EnvConfig()
    except Exception as e:
        raise ConfigValidationError(
            f"Failed to load environment variables: {e}\n"
            "Please ensure .env file exists with ATLASSIAN_EMAIL and ATLASSIAN_API_TOKEN"
        )
