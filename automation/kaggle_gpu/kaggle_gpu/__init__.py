"""
Kaggle GPU Integration — Multi-Account, Multi-Channel
Shared module for YouTube automation pipelines.

Usage:
    from kaggle_gpu import KaggleGPU, GPUTask

    gpu = KaggleGPU()
    result = gpu.run_task(
        task=GPUTask.SDXL_IMAGE,
        payload={"prompt": "a sunset over mountains"},
        estimated_hours=0.5
    )
    if result:
        image_path = result["output_path"]
    else:
        # Fallback to CPU/free APIs
        image_path = fallback_generate(prompt)
"""

from .config import KaggleConfig
from .accounts import AccountManager
from .budget import BudgetTracker
from .state import JobState, JobRecord, StateManager
from .client import KaggleClient, KaggleUnavailable
from .worker import KaggleGPU, GPUTask

__all__ = [
    "KaggleConfig",
    "AccountManager",
    "BudgetTracker",
    "JobState",
    "JobRecord",
    "StateManager",
    "KaggleClient",
    "KaggleUnavailable",
    "KaggleGPU",
    "GPUTask",
]
