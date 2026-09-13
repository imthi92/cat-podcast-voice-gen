"""Multi-account management for Kaggle GPU.

Supports multiple Kaggle accounts to distribute GPU load.
Each account gets its own 30hr/week budget.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class KaggleAccount:
    """A single Kaggle account credentials."""

    username: str
    api_key: str
    name: str = ""  # friendly name (e.g., "primary", "backup1")
    active: bool = True
    kaggle_json_path: str = ""

    def __post_init__(self):
        if not self.name:
            self.name = self.username

    def to_kaggle_json(self, path: str = None):
        """Write kaggle.json for this account."""
        path = path or self.kaggle_json_path
        if not path:
            path = str(Path.home() / ".kaggle" / f"kaggle_{self.username}.json")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump({"username": self.username, "key": self.api_key}, f)
        self.kaggle_json_path = path
        return path

    def set_as_current(self):
        """Set this account as the current active Kaggle account."""
        kaggle_dir = Path.home() / ".kaggle"
        kaggle_dir.mkdir(exist_ok=True)
        target = kaggle_dir / "kaggle.json"
        source = Path(self.kaggle_json_path)
        if source.exists():
            # Copy to standard location
            with open(source) as f:
                data = json.load(f)
            with open(target, "w") as f:
                json.dump(data, f)
            os.chmod(target, 0o600)


class AccountManager:
    """Manages multiple Kaggle accounts and selects the best one."""

    def __init__(self, config):
        self.config = config
        self.accounts: list[KaggleAccount] = []
        self._load_accounts()

    def _load_accounts(self):
        """Load accounts from config directory or environment."""

        # Method 1: KAGGLE_ACCOUNTS env var (JSON array)
        env_accounts = os.environ.get("KAGGLE_ACCOUNTS", "")
        if env_accounts:
            try:
                account_list = json.loads(env_accounts)
                for acc in account_list:
                    self.accounts.append(KaggleAccount(
                        username=acc["username"],
                        api_key=acc["api_key"],
                        name=acc.get("name", acc["username"]),
                    ))
                return
            except (json.JSONDecodeError, KeyError):
                pass

        # Method 2: Individual env vars (single account)
        username = os.environ.get("KAGGLE_USERNAME", "")
        api_key = os.environ.get("KAGGLE_KEY", "")
        if username and api_key:
            self.accounts.append(KaggleAccount(
                username=username,
                api_key=api_key,
                name="primary",
            ))

        # Method 3: kaggle.json files in accounts directory
        accounts_dir = Path(self.config.accounts_dir)
        if accounts_dir.exists():
            for f in accounts_dir.glob("kaggle_*.json"):
                try:
                    with open(f) as fh:
                        data = json.load(fh)
                    self.accounts.append(KaggleAccount(
                        username=data["username"],
                        api_key=data["key"],
                        name=f.stem.replace("kaggle_", ""),
                        kaggle_json_path=str(f),
                    ))
                except (json.JSONDecodeError, KeyError):
                    continue

        # Method 4: Default kaggle.json
        if not self.accounts:
            default_path = Path.home() / ".kaggle" / "kaggle.json"
            if default_path.exists():
                with open(default_path) as f:
                    data = json.load(f)
                self.accounts.append(KaggleAccount(
                    username=data.get("username", ""),
                    api_key=data.get("key", ""),
                    name="default",
                    kaggle_json_path=str(default_path),
                ))

    def get_available_accounts(self, budget_tracker) -> list[KaggleAccount]:
        """Return accounts that have remaining GPU budget this week."""
        available = []
        for acc in self.accounts:
            if not acc.active:
                continue
            remaining = budget_tracker.hours_remaining(acc.username)
            if remaining > 0.5:  # need at least 30 min remaining
                available.append(acc)
        return available

    def select_best_account(self, budget_tracker, estimated_hours: float) -> Optional[KaggleAccount]:
        """Select the account with the most remaining budget that can afford the job."""
        available = self.get_available_accounts(budget_tracker)
        if not available:
            return None

        # Sort by remaining budget (descending)
        available.sort(
            key=lambda a: budget_tracker.hours_remaining(a.username),
            reverse=True,
        )

        for acc in available:
            if budget_tracker.can_afford(acc.username, estimated_hours):
                return acc

        return None

    def get_total_remaining_hours(self, budget_tracker) -> float:
        """Total remaining GPU hours across all accounts."""
        total = 0.0
        for acc in self.accounts:
            if acc.active:
                total += budget_tracker.hours_remaining(acc.username)
        return total

    def get_account_count(self) -> int:
        return len([a for a in self.accounts if a.active])
