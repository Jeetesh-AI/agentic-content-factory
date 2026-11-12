"""SQLite-backed persistent job queue for unattended multi-stage video generation."""

import json
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, List, Optional


class JobQueue:
    """Thread-safe persistent job queue with stage tracking and retry counts."""

    def __init__(self, db_path: str = "content_jobs.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    artifact_path TEXT,
                    stage_timings_json TEXT,
                    error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            self._conn.commit()

    def enqueue(self, topic: str) -> str:
        job_id = f"job_{uuid.uuid4().hex[:10]}"
        now = time.time()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO jobs (id, topic, status, stage, attempts, created_at, updated_at)
                VALUES (?, ?, 'queued', 'pending', 0, ?, ?)
                """,
                (job_id, topic, now, now),
            )
            self._conn.commit()
        return job_id

    def claim_next(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            now = time.time()
            self._conn.execute(
                "UPDATE jobs SET status = 'running', stage = 'scripting', attempts = attempts + 1, updated_at = ? WHERE id = ?",
                (now, row["id"]),
            )
            self._conn.commit()
            return dict(row)

    def update_stage(self, job_id: str, stage: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET stage = ?, updated_at = ? WHERE id = ?",
                (stage, time.time(), job_id),
            )
            self._conn.commit()

    def complete(self, job_id: str, artifact_path: str, stage_timings: Dict[str, float]) -> None:
        with self._lock:
            self._conn.execute(
                """
                UPDATE jobs
                SET status = 'completed', stage = 'done', artifact_path = ?,
                    stage_timings_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (artifact_path, json.dumps(stage_timings), time.time(), job_id),
            )
            self._conn.commit()

    def fail(self, job_id: str, error: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status = 'failed', error = ?, updated_at = ? WHERE id = ?",
                (error, time.time(), job_id),
            )
            self._conn.commit()

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            return dict(row) if row else None

    def list_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
