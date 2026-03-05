"""Checkpoint management for resuming scraping operations."""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from .logger import get_logger

logger = get_logger()


class CheckpointManager:
    """Manage checkpoints for resumable scraping."""

    CHECKPOINT_FILE = "checkpoint.json"

    def __init__(self, checkpoint_file: str | Path = CHECKPOINT_FILE):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_file: Path to checkpoint file
        """
        self.checkpoint_file = Path(checkpoint_file)
        logger.debug(f"Checkpoint manager initialized: {self.checkpoint_file}")

    def save(self, state: Dict[str, Any]):
        """
        Save checkpoint state to file.

        Args:
            state: Current scraping state
        """
        # Add timestamp
        state["timestamp"] = datetime.now().isoformat()

        try:
            with open(self.checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)

            logger.info(f"✓ Checkpoint saved: {self.checkpoint_file}")

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    def load(self) -> Optional[Dict[str, Any]]:
        """
        Load checkpoint state from file.

        Returns:
            Checkpoint state or None if not exists
        """
        if not self.exists():
            return None

        try:
            with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                state = json.load(f)

            logger.info(f"✓ Checkpoint loaded from {state.get('timestamp', 'unknown time')}")
            return state

        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

    def clear(self):
        """
        Delete checkpoint file.
        """
        if self.exists():
            try:
                self.checkpoint_file.unlink()
                logger.info("✓ Checkpoint cleared")
            except Exception as e:
                logger.error(f"Failed to clear checkpoint: {e}")

    def exists(self) -> bool:
        """
        Check if checkpoint file exists.

        Returns:
            True if checkpoint exists
        """
        return self.checkpoint_file.exists()

    def create_state(
        self,
        jira_completed: bool = False,
        jira_data: list = None,
        jira_last_start_at: int = 0,
        jira_total: int = 0,
        confluence_completed: bool = False,
        confluence_data: list = None,
    ) -> Dict[str, Any]:
        """
        Create checkpoint state dictionary.

        Args:
            jira_completed: Whether Jira scraping is complete
            jira_data: Collected Jira issues
            jira_last_start_at: Last pagination offset
            jira_total: Total Jira issues
            confluence_completed: Whether Confluence scraping is complete
            confluence_data: Collected Confluence pages

        Returns:
            State dictionary
        """
        return {
            "jira": {
                "completed": jira_completed,
                "last_start_at": jira_last_start_at,
                "total": jira_total,
                "data": jira_data or [],
            },
            "confluence": {
                "completed": confluence_completed,
                "data": confluence_data or [],
            },
        }
