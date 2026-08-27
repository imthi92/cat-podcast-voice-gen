#!/usr/bin/env python3
"""
Deepnote Monitor — Polls GitHub for new commits and runs pipeline.
Alternative to webhook (works even if Deepnote has no public IP).
Run on Deepnote: python automation/monitor.py
"""

import os
import sys
import json
import subprocess
import time
import hashlib
from datetime import datetime
from pathlib import Path

CHECK_INTERVAL = 300  # 5 minutes
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_DIR = os.path.join(REPO_DIR, "automation")
STATE_FILE = os.path.join(SCRIPT_DIR, "monitor_state.json")


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def get_last_commit():
    """Get latest commit hash from remote."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", "origin", "HEAD"],
            cwd=REPO_DIR,
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode == 0:
            return result.stdout.strip().split()[0]
    except Exception as e:
        log(f"Error checking remote: {e}")
    return None


def load_state():
    """Load last known commit hash."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_commit": None}


def save_state(state):
    """Save commit hash."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def run_pipeline():
    """Run the podcast generator."""
    log("Running episode generator...")
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, "generate_episode.py")],
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True,
            timeout=1800
        )
        if result.returncode == 0:
            log("Episode generated successfully!")
            return True
        else:
            log(f"Generator failed: {result.stderr[-300:]}")
            return False
    except subprocess.TimeoutExpired:
        log("Generator timed out (30 min)")
        return False
    except Exception as e:
        log(f"Generator error: {e}")
        return False


def git_pull():
    """Pull latest changes."""
    try:
        subprocess.run(["git", "pull"], cwd=REPO_DIR, capture_output=True, timeout=30)
        log("Git pull complete")
    except Exception as e:
        log(f"Git pull failed: {e}")


def main():
    log("=" * 50)
    log("DEEPNOTE MONITOR — Starting")
    log(f"Checking every {CHECK_INTERVAL} seconds")
    log("=" * 50)

    state = load_state()

    while True:
        try:
            remote_commit = get_last_commit()
            local_commit = state.get("last_commit")

            if remote_commit and remote_commit != local_commit:
                log(f"New commit detected: {remote_commit[:8]}")
                git_pull()
                run_pipeline()
                state["last_commit"] = remote_commit
                state["last_run"] = datetime.now().isoformat()
                save_state(state)
            else:
                log(f"No changes (latest: {remote_commit[:8] if remote_commit else 'unknown'})")

        except Exception as e:
            log(f"Monitor error: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
