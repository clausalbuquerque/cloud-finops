from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from typing import Callable


JobAction = Callable[[], dict[str, object]]


@dataclass(frozen=True)
class OperationsSchedulerConfig:
    weekly_ingestion_interval_seconds: int = 7 * 24 * 60 * 60
    incremental_indexing_interval_seconds: int = 24 * 60 * 60
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0
    dead_letter_path: str = "docs/dead-letter-jobs.jsonl"


@dataclass(frozen=True)
class JobExecutionResult:
    job_name: str
    success: bool
    attempts: int
    payload: dict[str, object]


class OperationsScheduler:
    def __init__(self, config: OperationsSchedulerConfig | None = None) -> None:
        self._config = config or OperationsSchedulerConfig()

    @property
    def config(self) -> OperationsSchedulerConfig:
        return self._config

    def run_with_retry(self, job_name: str, action: JobAction) -> JobExecutionResult:
        last_error: Exception | None = None

        for attempt in range(1, self._config.max_retries + 1):
            try:
                payload = action()
                return JobExecutionResult(
                    job_name=job_name,
                    success=True,
                    attempts=attempt,
                    payload=payload,
                )
            except Exception as exc:
                last_error = exc
                if attempt < self._config.max_retries:
                    backoff = self._config.retry_backoff_seconds * (2 ** (attempt - 1))
                    sleep(backoff)

        failure_payload = {
            "job_name": job_name,
            "error": str(last_error) if last_error else "unknown",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._write_dead_letter(failure_payload)
        return JobExecutionResult(
            job_name=job_name,
            success=False,
            attempts=self._config.max_retries,
            payload=failure_payload,
        )

    def run_once(self, jobs: list[tuple[str, JobAction]]) -> list[JobExecutionResult]:
        return [self.run_with_retry(name, action) for name, action in jobs]

    def run_forever(self, jobs: list[tuple[str, int, JobAction]]) -> None:
        now = datetime.now(timezone.utc).timestamp()
        next_run_by_job = {name: now for name, _, _ in jobs}

        while True:
            now = datetime.now(timezone.utc).timestamp()
            for name, interval_seconds, action in jobs:
                if now >= next_run_by_job[name]:
                    self.run_with_retry(name, action)
                    next_run_by_job[name] = now + interval_seconds
            sleep(1.0)

    def _write_dead_letter(self, payload: dict[str, object]) -> None:
        path = Path(self._config.dead_letter_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
