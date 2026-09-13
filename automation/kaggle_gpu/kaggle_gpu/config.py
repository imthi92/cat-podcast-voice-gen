"""Configuration for Kaggle GPU integration."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class KaggleConfig:
    """All configuration for Kaggle GPU integration."""

    # Account credentials (loaded from env or kaggle.json files)
    # Multiple accounts supported via KAGGLE_ACCOUNTS env or config files
    accounts_dir: str = field(
        default_factory=lambda: os.environ.get(
            "KAGGLE_ACCOUNTS_DIR",
            str(Path.home() / ".kaggle" / "accounts"),
        )
    )

    # State persistence
    state_dir: str = field(
        default_factory=lambda: os.environ.get(
            "KAGGLE_STATE_DIR",
            str(Path.home() / ".kaggle_gpu_state"),
        )
    )
    budget_path: str = field(
        default_factory=lambda: os.environ.get(
            "KAGGLE_BUDGET_PATH",
            str(Path.home() / ".kaggle_gpu_budget.json"),
        )
    )

    # Retry settings
    max_retries: int = 3
    retry_interval_sec: int = 1800  # 30 minutes
    retry_backoff_multiplier: float = 2.0  # 30min -> 60min -> 120min

    # Runtime limits
    max_runtime_hours: float = 8.5  # safety margin under 9hr session limit
    poll_interval_sec: int = 60  # check every 60 seconds

    # Budget
    weekly_budget_hours: float = 30.0  # per account

    # Notebook
    notebook_slug: str = "kaggle-gpu-worker"
    dataset_slug: str = ""  # optional: for storing large model weights

    # Output
    output_base_dir: str = field(
        default_factory=lambda: os.environ.get(
            "KAGGLE_OUTPUT_DIR",
            str(Path.home() / ".kaggle_gpu_output"),
        )
    )

    # Estimated hours per task type (for budget planning)
    task_estimates: dict = field(default_factory=lambda: {
        "sdxl_image": 0.15,    # ~9 min per image batch
        "xtts_voice": 0.10,    # ~6 min per voice clip
        "sadtalker": 0.25,     # ~15 min per animation
        "vibevoice": 0.20,     # ~12 min per voice clip
        "whisper": 0.30,       # ~18 min per transcription
    })

    @classmethod
    def from_env(cls) -> "KaggleConfig":
        """Create config from environment variables."""
        return cls()

    def ensure_dirs(self):
        """Create required directories."""
        Path(self.state_dir).mkdir(parents=True, exist_ok=True)
        Path(self.output_base_dir).mkdir(parents=True, exist_ok=True)
        Path(self.accounts_dir).mkdir(parents=True, exist_ok=True)
