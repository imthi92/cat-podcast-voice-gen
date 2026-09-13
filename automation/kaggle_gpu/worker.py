"""High-level GPU task orchestration with multi-account support.

This is the main public API that consuming repos use.
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

from .config import KaggleConfig
from .accounts import AccountManager
from .budget import BudgetTracker
from .state import JobState, JobRecord, StateManager, GPUTask
from .client import KaggleClient, KaggleUnavailable

logger = logging.getLogger(__name__)


class KaggleGPU:
    """Main interface for Kaggle GPU integration.

    Usage:
        gpu = KaggleGPU(project_name="ai-content-network")
        result = gpu.run_task(
            task=GPUTask.SDXL_IMAGE,
            payload={"prompt": "a sunset", "width": 1024, "height": 1024},
        )
        if result:
            path = result["output_path"]
        else:
            path = fallback_generate(prompt)
    """

    def __init__(
        self,
        project_name: str = "default",
        config: KaggleConfig = None,
    ):
        self.config = config or KaggleConfig()
        self.config.ensure_dirs()

        self.accounts = AccountManager(self.config)
        self.budget = BudgetTracker(
            self.config.budget_path,
            self.config.weekly_budget_hours,
        )
        self.state = StateManager(project_name, self.config.state_dir)
        self.client = KaggleClient(self.config)

        self.project_name = project_name
        self._disabled = self.accounts.get_account_count() == 0

        if self._disabled:
            logger.warning(
                "Kaggle GPU disabled: no accounts configured. "
                "Set KAGGLE_USERNAME + KAGGLE_KEY or KAGGLE_ACCOUNTS env vars."
            )

    @property
    def is_available(self) -> bool:
        """Check if Kaggle is usable right now."""
        if self._disabled:
            return False
        total = self.budget.get_summary().get("total_remaining", 0)
        return total > 0.5

    def get_status(self) -> dict:
        """Get current Kaggle integration status."""
        budget_summary = self.budget.get_summary()
        pending = self.state.get_pending_jobs()
        return {
            "enabled": not self._disabled,
            "accounts": self.accounts.get_account_count(),
            "budget": budget_summary,
            "pending_jobs": len(pending),
            "is_available": self.is_available,
        }

    def run_task(
        self,
        task: GPUTask,
        payload: dict,
        estimated_hours: float = None,
    ) -> Optional[dict]:
        """Run a GPU task on Kaggle with automatic account selection and fallback.

        Args:
            task: Type of GPU task
            payload: Task-specific parameters (passed to Kaggle notebook)
            estimated_hours: Override estimated hours (or use config default)

        Returns:
            dict with result info if successful, None if fallback needed
        """
        if self._disabled:
            logger.info(f"Kaggle disabled, skipping {task.value}")
            return None

        # Estimate hours if not provided
        if estimated_hours is None:
            estimated_hours = self.config.task_estimates.get(task.value, 0.25)

        # Check budget across all accounts
        account = self.accounts.select_best_account(self.budget, estimated_hours)
        if not account:
            logger.info(
                f"No Kaggle account has budget for {task.value} "
                f"(estimated {estimated_hours}h). Budget exhausted."
            )
            return None

        # Create job record
        job = self.state.create_job(task, payload, estimated_hours)

        # Execute with retries
        return self._execute_with_retries(job, account, estimated_hours)

    def _execute_with_retries(
        self,
        job: JobRecord,
        account,
        estimated_hours: float,
    ) -> Optional[dict]:
        """Execute job with retry logic."""
        max_attempts = job.max_attempts
        retry_interval = self.config.retry_interval_sec

        for attempt in range(1, max_attempts + 1):
            try:
                # Set this account as active
                account.set_as_current()

                # Update state
                self.state.update_job(
                    job.job_id,
                    state=JobState.SUBMITTED.value,
                    account_username=account.username,
                    attempts=attempt,
                )

                # Submit to Kaggle
                logger.info(
                    f"[{job.job_id}] Submitting {job.task} to Kaggle "
                    f"(account: {account.username}, attempt {attempt}/{max_attempts})"
                )

                kernel_slug = self.client.submit_kernel(
                    account=account,
                    notebook_slug=self.config.notebook_slug,
                    parameters={
                        "task_type": job.task,
                        "payload_json": json.dumps(job.payload),
                        "job_id": job.job_id,
                        "output_dir": str(
                            Path(self.config.output_base_dir) / job.job_id
                        ),
                    },
                    kernel_title=f"{self.project_name}_{job.task}_{job.job_id}",
                )

                self.state.update_job(
                    job.job_id,
                    state=JobState.WAITING.value,
                    kernel_run_id=kernel_slug,
                )

                # Wait for completion
                result = self.client.wait_for_kernel(
                    account=account,
                    kernel_slug=kernel_slug,
                    poll_interval=self.config.poll_interval_sec,
                    max_wait=int(self.config.max_runtime_hours * 3600),
                )

                # Download results
                output_dir = str(Path(self.config.output_base_dir) / job.job_id)
                downloaded_files = self.client.download_output(
                    account=account,
                    kernel_slug=kernel_slug,
                    dest_dir=output_dir,
                )

                # Calculate actual hours used
                elapsed_hours = result.get("elapsed_seconds", 0) / 3600
                actual_hours = max(0.01, elapsed_hours)  # minimum 0.01 to track

                # Record budget usage
                self.budget.record_usage(
                    username=account.username,
                    kernel_run_id=kernel_slug,
                    hours=actual_hours,
                    task=job.task,
                )

                # Mark complete
                self.state.update_job(
                    job.job_id,
                    state=JobState.COMPLETED.value,
                    result_paths=downloaded_files,
                    actual_hours=actual_hours,
                    output_dir=output_dir,
                )

                logger.info(
                    f"[{job.job_id}] Completed on {account.username} "
                    f"({actual_hours:.2f}h GPU used, {len(downloaded_files)} files)"
                )

                return {
                    "job_id": job.job_id,
                    "status": "completed",
                    "account": account.username,
                    "output_dir": output_dir,
                    "output_files": downloaded_files,
                    "gpu_hours": actual_hours,
                    "kernel_slug": kernel_slug,
                }

            except KaggleUnavailable as e:
                error_msg = str(e)
                logger.warning(
                    f"[{job.job_id}] Attempt {attempt}/{max_attempts} failed: {error_msg}"
                )

                self.state.update_job(
                    job.job_id,
                    state=JobState.RETRYING.value,
                    error=error_msg,
                )

                # Check if we should retry
                if attempt < max_attempts:
                    wait_time = retry_interval * (
                        self.config.retry_backoff_multiplier ** (attempt - 1)
                    )
                    logger.info(
                        f"[{job.job_id}] Waiting {wait_time/60:.0f}min before retry..."
                    )
                    time.sleep(wait_time)

                    # Try a different account if available
                    new_account = self.accounts.select_best_account(
                        self.budget, estimated_hours
                    )
                    if new_account and new_account.username != account.username:
                        account = new_account
                        logger.info(f"[{job.job_id}] Switching to account: {account.username}")

        # All retries exhausted
        self.state.update_job(
            job.job_id,
            state=JobState.FAILED.value,
            error=f"All {max_attempts} attempts failed. Last error: {error_msg}",
        )

        logger.error(
            f"[{job.job_id}] FAILED after {max_attempts} attempts. "
            "Falling back to non-GPU pipeline."
        )
        return None

    def process_waiting_jobs(self):
        """Process any jobs stuck in WAITING or RETRYING state."""
        pending = self.state.get_pending_jobs()
        for job in pending:
            if job.state == JobState.WAITING.value and job.kernel_run_id:
                # Check if kernel is still running
                account = self._find_account(job.account_username)
                if account:
                    try:
                        status = self.client.poll_kernel(account, job.kernel_run_id)
                        if status == "complete":
                            # Re-download and complete
                            logger.info(f"[{job.job_id}] Resuming completed job")
                            # ... (similar to completion logic)
                    except KaggleUnavailable:
                        pass

    def _find_account(self, username: str):
        """Find account by username."""
        for acc in self.accounts.accounts:
            if acc.username == username and acc.active:
                return acc
        return None

    def cancel_all(self):
        """Cancel all pending/waiting jobs."""
        for job in self.state.get_pending_jobs():
            if job.kernel_run_id:
                account = self._find_account(job.account_username)
                if account:
                    self.client.cancel_kernel(account, job.kernel_run_id)
            self.state.update_job(job.job_id, state=JobState.FAILED.value, error="Cancelled")
