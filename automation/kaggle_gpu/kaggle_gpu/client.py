"""Kaggle API client for kernel submission, polling, and result download."""

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class KaggleUnavailable(Exception):
    """Raised when Kaggle cannot be used (budget, API error, etc.)."""
    pass


class KaggleClient:
    """Low-level Kaggle API operations."""

    def __init__(self, config):
        self.config = config
        self._validate_kaggle_api()

    def _validate_kaggle_api(self):
        """Check if kaggle CLI is available."""
        try:
            result = subprocess.run(
                ["kaggle", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                logger.warning("Kaggle CLI not found or not working")
        except FileNotFoundError:
            logger.warning("Kaggle CLI not installed. Install with: pip install kaggle")

    def _run_kaggle_cmd(self, args: list[str], timeout: int = 60, env: dict = None) -> dict:
        """Run a kaggle CLI command and return parsed JSON output."""
        cmd = ["kaggle"] + args + ["--json"]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, **(env or {})},
            )
            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                raise KaggleUnavailable(f"Kaggle API error: {error_msg}")

            # Parse JSON output
            output = result.stdout.strip()
            if output:
                return json.loads(output)
            return {}

        except subprocess.TimeoutExpired:
            raise KaggleUnavailable("Kaggle API timeout")
        except json.JSONDecodeError as e:
            raise KaggleUnavailable(f"Kaggle API invalid response: {e}")

    def set_account_env(self, account) -> dict:
        """Set environment variables for a specific account."""
        return {
            "KAGGLE_USERNAME": account.username,
            "KAGGLE_KEY": account.api_key,
        }

    def check_quota(self, account) -> dict:
        """Check GPU quota for an account."""
        env = self.set_account_env(account)
        try:
            result = self._run_kaggle_cmd(["kernels", "list"], env=env)
            return {"available": True, "account": account.username, "quotas": result}
        except KaggleUnavailable as e:
            return {"available": False, "account": account.username, "error": str(e)}

    def submit_kernel(
        self,
        account,
        notebook_slug: str,
        parameters: dict,
        kernel_title: str = "",
    ) -> str:
        """Submit a Kaggle kernel run with parameters.

        Returns: kernel run ID
        Raises: KaggleUnavailable
        """
        env = self.set_account_env(account)

        # Build parameters string
        params_json = json.dumps(parameters)

        # Create a version of the notebook with injected parameters
        # We use papermill-style parameter injection
        cmd_args = [
            "kernels", "push",
            "-p", str(Path(__file__).parent.parent / "notebooks"),  # local notebook path
            "-k", f"{account.username}/{notebook_slug}",
            "-m", kernel_title or f"gpu_job_{int(time.time())}",
        ]

        # Add environment variables for parameter injection
        env["KAGGLE_GPU_TASK_PARAMS"] = params_json

        try:
            result = self._run_kaggle_cmd(cmd_args, timeout=120, env=env)
            kernel_id = result.get("ref", result.get("id", ""))
            if not kernel_id:
                # Try to extract from output
                kernel_id = f"{account.username}/{notebook_slug}"
            logger.info(f"Kernel submitted: {kernel_id} on account {account.username}")
            return kernel_id
        except KaggleUnavailable as e:
            raise KaggleUnavailable(f"Failed to submit kernel: {e}")

    def poll_kernel(self, account, kernel_slug: str) -> str:
        """Poll kernel status.

        Returns: status string (running, complete, error, etc.)
        Raises: KaggleUnavailable
        """
        env = self.set_account_env(account)
        try:
            result = self._run_kaggle_cmd(
                ["kernels", "status", kernel_slug],
                env=env,
            )
            status = result.get("status", "unknown")
            return status.lower()
        except KaggleUnavailable as e:
            raise KaggleUnavailable(f"Failed to poll kernel: {e}")

    def wait_for_kernel(
        self,
        account,
        kernel_slug: str,
        poll_interval: int = 60,
        max_wait: int = 36000,  # 10 hours
    ) -> dict:
        """Wait for kernel to complete.

        Returns: {"status": "complete", "runtime_minutes": 45, ...}
        Raises: KaggleUnavailable on timeout or error
        """
        start_time = time.time()
        attempts = 0

        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait:
                raise KaggleUnavailable(f"Kernel timed out after {max_wait}s")

            try:
                status = self.poll_kernel(account, kernel_slug)
                attempts += 1

                if status in ("complete", "running"):
                    if status == "complete":
                        logger.info(f"Kernel complete after {elapsed:.0f}s")
                        return {"status": "complete", "elapsed_seconds": elapsed}
                    # Still running, wait and poll again
                    time.sleep(poll_interval)
                    continue

                elif status in ("error", "failed"):
                    raise KaggleUnavailable(f"Kernel failed with status: {status}")

                elif status == "queued":
                    # Still queued, wait longer
                    time.sleep(poll_interval * 2)
                    continue

                else:
                    # Unknown status, keep polling
                    time.sleep(poll_interval)
                    continue

            except KaggleUnavailable as e:
                if "timeout" in str(e).lower():
                    raise
                # Transient error, retry a few times
                if attempts > 5:
                    raise
                time.sleep(poll_interval)
                continue

    def download_output(self, account, kernel_slug: str, dest_dir: str) -> list[str]:
        """Download kernel output files.

        Returns: list of downloaded file paths
        Raises: KaggleUnavailable
        """
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)

        env = self.set_account_env(account)
        try:
            result = self._run_kaggle_cmd(
                ["kernels", "pull", kernel_slug, "-p", str(dest)],
                timeout=300,
                env=env,
            )
            # List downloaded files
            downloaded = list(dest.glob("**/*"))
            return [str(f) for f in downloaded if f.is_file()]
        except KaggleUnavailable as e:
            raise KaggleUnavailable(f"Failed to download output: {e}")

    def cancel_kernel(self, account, kernel_slug: str) -> bool:
        """Cancel a running kernel."""
        env = self.set_account_env(account)
        try:
            self._run_kaggle_cmd(
                ["kernels", "cancel", kernel_slug],
                env=env,
            )
            return True
        except KaggleUnavailable:
            return False
