"""Tests for SQLite JobQueue and 4-stage ContentPipelineWorker."""

import os
from pathlib import Path
import tempfile

from fastapi.testclient import TestClient

from app.agents import ContentPipelineWorker
from app.main import app
from app.queue import JobQueue


def test_job_queue_and_worker_end_to_end() -> None:
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    with tempfile.TemporaryDirectory() as tmp_dir:
        q = JobQueue(db_path=db_path)
        w = ContentPipelineWorker(queue=q, output_root=Path(tmp_dir))

        job_id = q.enqueue("Hybrid RAG with Citations")
        done = w.process_next()

        assert done is not None
        assert done["id"] == job_id
        assert done["status"] == "completed"
        assert Path(done["artifact_path"]).exists()
        q.close()
    os.remove(db_path)


def test_fastapi_jobs_lifecycle() -> None:
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    r = client.post("/jobs", json={"topic": "Voice Agents"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    proc = client.post("/jobs/process-next")
    assert proc.status_code == 200
    assert proc.json()["processed"] is True

    status = client.get(f"/jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "completed"
