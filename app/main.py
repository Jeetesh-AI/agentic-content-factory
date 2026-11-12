"""FastAPI service & UI for Agentic Content Factory."""

from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.agents import ContentPipelineWorker
from app.queue import JobQueue

ROOT = Path(__file__).resolve().parent.parent
queue = JobQueue(str(ROOT / "content_jobs.db"))
worker = ContentPipelineWorker(queue=queue, output_root=ROOT / "artifacts")
app = FastAPI(title="Agentic Content Factory", version="1.0.0")


class CreateJobRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=200)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/jobs")
def create_job(req: CreateJobRequest) -> Dict[str, str]:
    job_id = queue.enqueue(req.topic)
    return {"job_id": job_id, "status": "queued"}


@app.post("/jobs/process-next")
def process_next() -> Dict[str, Any]:
    job = worker.process_next()
    if not job:
        return {"processed": False, "message": "Queue is empty"}
    return {"processed": True, "job": job}


@app.get("/jobs")
def list_jobs() -> List[Dict[str, Any]]:
    return queue.list_jobs()


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> Dict[str, Any]:
    job = queue.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/", response_class=HTMLResponse)
def ui() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Agentic Content Factory</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; background: #0d1117; color: #e6edf3; }
    h1 { color: #a78bfa; }
    .row { display: flex; gap: 8px; margin: 16px 0; }
    input { flex: 1; padding: 12px; border-radius: 8px; border: 1px solid #30363d; background: #161b22; color: #e6edf3; }
    button { padding: 12px 18px; border-radius: 8px; border: 0; background: #7c3aed; color: white; font-weight: 600; cursor: pointer; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 14px; margin-top: 12px; }
  </style>
</head>
<body>
  <h1>Agentic Content Factory</h1>
  <p>Queue a story idea and run the 4-stage pipeline: Script → Narration → Visuals → Vertical Cut.</p>
  <div class="row">
    <input id="topic" value="How LLM admission control prevents tail-latency collapse" />
    <button onclick="runJob()">Queue &amp; Render</button>
  </div>
  <div id="out"></div>
  <script>
    async function runJob() {
      const topic = document.getElementById('topic').value;
      await fetch('/jobs', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ topic }) });
      const res = await fetch('/jobs/process-next', { method: 'POST' });
      const data = await res.json();
      document.getElementById('out').innerHTML = `<div class="card"><pre>${JSON.stringify(data.job, null, 2)}</pre></div>`;
    }
  </script>
</body>
</html>"""
