"""Weekly GPU budget tracking per account."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class BudgetTracker:
    """Tracks GPU hours used per account per week."""

    def __init__(self, budget_path: str, weekly_budget_hours: float = 30.0):
        self.budget_path = Path(budget_path)
        self.weekly_budget_hours = weekly_budget_hours
        self._data = self._load()

    def _get_week_key(self) -> str:
        """Current ISO week key (e.g., '2026-W37')."""
        now = datetime.now(timezone.utc)
        return f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"

    def _load(self) -> dict:
        """Load budget data from file."""
        if self.budget_path.exists():
            try:
                with open(self.budget_path) as f:
                    data = json.load(f)
                # Reset if new week
                if data.get("week") != self._get_week_key():
                    return self._fresh_data()
                return data
            except (json.JSONDecodeError, KeyError):
                return self._fresh_data()
        return self._fresh_data()

    def _fresh_data(self) -> dict:
        return {
            "week": self._get_week_key(),
            "accounts": {},
        }

    def _save(self):
        """Atomic write to budget file."""
        self.budget_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(self.budget_path) + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self._data, f, indent=2)
        Path(tmp).replace(self.budget_path)

    def _ensure_week(self):
        """Reset data if we're in a new week."""
        if self._data.get("week") != self._get_week_key():
            self._data = self._fresh_data()
            self._save()

    def _get_account_data(self, username: str) -> dict:
        self._ensure_week()
        if username not in self._data["accounts"]:
            self._data["accounts"][username] = {
                "total_hours_used": 0.0,
                "runs": [],
            }
        return self._data["accounts"][username]

    def hours_used(self, username: str) -> float:
        """Hours used this week by this account."""
        acc = self._get_account_data(username)
        return acc.get("total_hours_used", 0.0)

    def hours_remaining(self, username: str) -> float:
        """Hours remaining this week for this account."""
        return max(0.0, self.weekly_budget_hours - self.hours_used(username))

    def can_afford(self, username: str, estimated_hours: float) -> bool:
        """Check if account has enough budget for estimated job."""
        return self.hours_remaining(username) >= estimated_hours

    def record_usage(self, username: str, kernel_run_id: str, hours: float, task: str):
        """Record GPU usage after a job completes."""
        acc = self._get_account_data(username)
        acc["total_hours_used"] = round(acc["total_hours_used"] + hours, 3)
        acc["runs"].append({
            "kernel_run_id": kernel_run_id,
            "hours": round(hours, 3),
            "task": task,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._save()

    def get_summary(self) -> dict:
        """Get summary of all accounts."""
        self._ensure_week()
        summary = {
            "week": self._data["week"],
            "accounts": {},
            "total_remaining": 0.0,
        }
        for username, acc_data in self._data.get("accounts", {}).items():
            used = acc_data.get("total_hours_used", 0.0)
            remaining = max(0.0, self.weekly_budget_hours - used)
            summary["accounts"][username] = {
                "used": used,
                "remaining": remaining,
                "runs": len(acc_data.get("runs", [])),
            }
            summary["total_remaining"] += remaining

        return summary
