"""Job state machine and persistence."""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


class JobState(Enum):
    QUEUED = "queued"
    SUBMITTED = "submitted"
    WAITING = "waiting"
    COMPLETED = "completed"
    RETRYING = "retrying"
    FAILED = "failed"
    SKIPPED = "skipped"


class GPUTask(Enum):
    SDXL_IMAGE = "sdxl_image"
    XTTS_VOICE = "xtts_voice"
    SADTALKER = "sadtalker"
    VIBEVOICE = "vibevoice"
    WHISPER = "whisper"


@dataclass
class JobRecord:
    job_id: str
    task: str  # GPUTask.value
    payload: dict
    state: str  # JobState.value
    account_username: str = ""
    kernel_run_id: str = ""
    attempts: int = 0
    max_attempts: int = 3
    created_at: str = ""
    updated_at: str = ""
    result_paths: list = field(default_factory=list)
    output_dir: str = ""
    error: str = ""
    estimated_hours: float = 0.0
    actual_hours: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "JobRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class StateManager:
    """Persistent job state management."""

    def __init__(self, project_name: str, state_dir: str):
        self.state_dir = Path(state_dir) / project_name
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_file = self.state_dir / "jobs.json"
        self._jobs: dict[str, JobRecord] = {}
        self._load()

    def _load(self):
        if self.jobs_file.exists():
            try:
                with open(self.jobs_file) as f:
                    data = json.load(f)
                for job_id, job_data in data.items():
                    self._jobs[job_id] = JobRecord.from_dict(job_data)
            except (json.JSONDecodeError, KeyError):
                self._jobs = {}

    def _save(self):
        tmp = str(self.jobs_file) + ".tmp"
        with open(tmp, "w") as f:
            json.dump({jid: j.to_dict() for jid, j in self._jobs.items()}, f, indent=2)
        Path(tmp).replace(self.jobs_file)

    def create_job(
        self,
        task: GPUTask,
        payload: dict,
        estimated_hours: float = 0.0,
    ) -> JobRecord:
        """Create a new job record."""
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job = JobRecord(
            job_id=job_id,
            task=task.value,
            payload=payload,
            state=JobState.QUEUED.value,
            estimated_hours=estimated_hours,
        )
        self._jobs[job_id] = job
        self._save()
        return job

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        return self._jobs.get(job_id)

    def update_job(self, job_id: str, **fields):
        """Update job fields and save."""
        job = self._jobs.get(job_id)
        if not job:
            return
        for key, value in fields.items():
            if hasattr(job, key):
                setattr(job, key, value)
        job.updated_at = datetime.now(timezone.utc).isoformat()
        self._save()

    def get_jobs_by_state(self, state: JobState) -> list[JobRecord]:
        """Get all jobs in a given state."""
        return [j for j in self._jobs.values() if j.state == state.value]

    def get_pending_jobs(self) -> list[JobRecord]:
        """Get jobs that need attention (queued, retrying, waiting)."""
        return [
            j for j in self._jobs.values()
            if j.state in (
                JobState.QUEUED.value,
                JobState.RETRYING.value,
                JobState.WAITING.value,
            )
        ]

    def cleanup_old_jobs(self, max_age_days: int = 7):
        """Remove completed/failed jobs older than N days."""
        cutoff = datetime.now(timezone.utc).timestamp() - (max_age_days * 86400)
        to_remove = []
        for job_id, job in self._jobs.items():
            if job.state in (JobState.COMPLETED.value, JobState.FAILED.value):
                try:
                    created = datetime.fromisoformat(job.created_at).timestamp()
                    if created < cutoff:
                        to_remove.append(job_id)
                except (ValueError, TypeError):
                    pass
        for job_id in to_remove:
            del self._jobs[job_id]
        if to_remove:
            self._save()
