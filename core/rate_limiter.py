"""Rate limiter — tracks actions per hour to stay within Instagram limits.

Uses a sliding window approach: stores timestamps of each action
and counts how many fall within the last 60 minutes.
"""

import json
import time
from pathlib import Path
from collections import defaultdict

from config import settings


class RateLimiter:
    """Track and enforce per-action hourly rate limits."""

    def __init__(self, log_path: Path | None = None):
        self.log_path = log_path or settings.LOG_PATH
        self.actions: dict[str, list[float]] = defaultdict(list)
        self._load()

    def _load(self):
        """Load action history from disk."""
        if self.log_path.exists():
            try:
                data = json.loads(self.log_path.read_text())
                for action_type, timestamps in data.get("rate_log", {}).items():
                    self.actions[action_type] = timestamps
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self):
        """Persist action history to disk."""
        # Load existing log to avoid overwriting other data
        existing = {}
        if self.log_path.exists():
            try:
                existing = json.loads(self.log_path.read_text())
            except json.JSONDecodeError:
                pass

        existing["rate_log"] = dict(self.actions)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text(json.dumps(existing, indent=2))

    def _clean_old(self, action_type: str):
        """Remove timestamps older than 1 hour."""
        cutoff = time.time() - 3600
        self.actions[action_type] = [
            t for t in self.actions[action_type] if t > cutoff
        ]

    def can_perform(self, action_type: str) -> bool:
        """Check if we can perform this action without exceeding limits."""
        self._clean_old(action_type)
        limit = settings.RATE_LIMITS.get(action_type, 30)
        return len(self.actions[action_type]) < limit

    def record(self, action_type: str, target: str = ""):
        """Record that an action was performed."""
        self.actions[action_type].append(time.time())
        self._save()

        count = len(self.actions[action_type])
        limit = settings.RATE_LIMITS.get(action_type, 30)
        print(f"[rate] {action_type} → {count}/{limit} this hour" +
              (f" (target: {target})" if target else ""))

    def remaining(self, action_type: str) -> int:
        """How many more actions of this type can be performed this hour."""
        self._clean_old(action_type)
        limit = settings.RATE_LIMITS.get(action_type, 30)
        return max(0, limit - len(self.actions[action_type]))

    def status(self) -> dict[str, str]:
        """Get a summary of all rate limits."""
        result = {}
        for action_type, limit in settings.RATE_LIMITS.items():
            self._clean_old(action_type)
            used = len(self.actions[action_type])
            result[action_type] = f"{used}/{limit}"
        return result
