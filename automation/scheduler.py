#!/usr/bin/env python3
"""
Scheduler - Run automation daily
This script runs the master automation and can be scheduled via Task Scheduler (Windows) or cron (Linux/Mac)
"""

import os
import sys
import subprocess
from datetime import datetime

# Configuration
AUTOMATION_DIR = r"C:\Users\Imtiyaz\Documents\New OpenCode Project\automation"
PYTHON_EXE = sys.executable

# Environment variables - set these before running or in .env file
ENV_VARS = {
    "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
    "COLAB_WEBHOOK_URL": os.environ.get("COLAB_WEBHOOK_URL", ""),
}

def run_automation():
    """Run the master automation script."""
    print(f"\n{'='*60}")
    print(f"AUTOMATION RUN: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    # Set environment variables
    for key, value in ENV_VARS.items():
        os.environ[key] = value

    # Change to automation directory
    os.chdir(AUTOMATION_DIR)

    # Run master automation
    cmd = [PYTHON_EXE, "master_automation.py"]
    result = subprocess.run(cmd, capture_output=False)

    print(f"\n{'='*60}")
    print(f"RUN COMPLETE: {datetime.now().isoformat()}")
    print(f"Exit code: {result.returncode}")
    print(f"{'='*60}\n")

    return result.returncode


if __name__ == "__main__":
    run_automation()