"""Logging configuration using rich for colored console output."""

import logging
import sys
from pathlib import Path
from datetime import datetime
from rich.logging import RichHandler
from rich.console import Console

# Create console for rich output
console = Console()

# Create logs directory if it doesn't exist
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

# Generate log filename with timestamp
log_filename = LOGS_DIR / f"scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"


def setup_logger(name: str = "scraper", level: str = "INFO") -> logging.Logger:
    """
    Set up logger with both console (rich) and file handlers.

    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Convert string level to logging constant
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Console handler with rich formatting
    console_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        markup=True,
    )
    console_handler.setLevel(log_level)
    console_format = logging.Formatter(
        "%(message)s",
        datefmt="[%X]"
    )
    console_handler.setFormatter(console_format)

    # File handler with detailed formatting
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)  # Always log DEBUG to file
    file_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_format)

    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "scraper") -> logging.Logger:
    """Get existing logger instance."""
    return logging.getLogger(name)


def mask_token(token: str) -> str:
    """
    Mask API token for safe logging.

    Args:
        token: API token to mask

    Returns:
        Masked token showing only first and last 4 characters
    """
    if not token or len(token) < 12:
        return "***"
    return f"{token[:4]}...{token[-4:]}"
