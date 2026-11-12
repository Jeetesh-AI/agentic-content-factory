"""Benchmarks 5 unattended jobs through the worker queue and generates SVG charts."""

import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agents import ContentPipelineWorker
from app.queue import JobQueue

THEMES = {
    "light": {"bg": "#ffffff", "card": "#f8fafc", "border": "#cbd5e1", "text": "#0f172a", "muted": "#475569", "accent": "#6d28d9", "good": "#16a34a", "info": "#0284c7"},
    "dark": {"bg": "#0d1117", "card": "#161b22", "border": "#30363d", "text": "#e6edf3", "muted": "#8b949e", "accent": "#a78bfa", "good": "#4ade80", "info": "#38bdf8"},
}


def build_pipeline_svg(theme: str) -> str:
    t = THEMES[theme]
    w, h = 760, 200
    stages = [
        (24, 65, 120, 70, "Job Queue", "SQLite FIFO", t["muted"]),
        (170, 65, 120, 70, "Script Agent", "3-Scene Hook", t["accent"]),
        (316, 65, 125, 70, "Narration", "WAV Synthesis", t["info"]),
        (467, 65, 120, 70, "Visuals", "9:16 Frames", t["accent"]),
        (613, 65, 122, 70, "Cut Agent", "FFmpeg / Pack", t["good"]),
    ]
    nodes = "".join(
        f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="10" fill="{t["card"]}" stroke="{col}" stroke-width="2" />'
        f'<text x="{x + bw / 2:.1f}" y="{y + 28}" text-anchor="middle" fill="{t["text"]}" font-size="13" font-weight="700" font-family="ui-sans-serif, system-ui">{title}</text>'
        f'<text x="{x + bw / 2:.1f}" y="{y + 48}" text-anchor="middle" fill="{t["muted"]}" font-size="11" font-family="ui-sans-serif, system-ui">{sub}</text>'
        for x, y, bw, bh, title, sub, col in stages
    )
    arrows = [(144, 100, 170, 100), (290, 100, 316, 100), (441, 100, 467, 100), (587, 100, 613, 100)]
    arr_svg = "".join(
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{t["muted"]}" stroke-width="2" marker-end="url(#arr)" />'
        for x1, y1, x2, y2 in arrows
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <defs><marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="{t['muted']}" /></marker></defs>
  <rect width="{w}" height="{h}" rx="12" fill="{t['bg']}" stroke="{t['border']}" />
  <text x="24" y="34" fill="{t['text']}" font-size="15" font-weight="700" font-family="ui-sans-serif, system-ui">Unattended Multi-Agent Vertical Video Pipeline</text>
  {arr_svg}
  {nodes}
</svg>
"""


def main() -> None:
    topics = [
        "Admission control in LLM gateways",
        "Hybrid BM25 and vector retrieval",
        "Low-latency voice agent pipelines",
        "Quantizing LLMs for edge GPUs",
        "Automated evals for RAG citations",
    ]
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    with tempfile.TemporaryDirectory() as tmp_dir:
        q = JobQueue(db_path=db_path)
        w = ContentPipelineWorker(queue=q, output_root=Path(tmp_dir))
        for t in topics:
            q.enqueue(t)

        t0 = time.perf_counter()
        completed = 0
        while True:
            res = w.process_next()
            if not res:
                break
            if res["status"] == "completed":
                completed += 1
        total_ms = round((time.perf_counter() - t0) * 1000, 1)
        q.close()
    os.remove(db_path)

    summary = {
        "jobs_queued": len(topics),
        "jobs_completed": completed,
        "completion_rate_pct": round((completed / len(topics)) * 100, 1),
        "batch_total_ms": total_ms,
        "avg_job_ms": round(total_ms / len(topics), 1),
    }

    (ROOT / "docs" / "results").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs" / "img").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs" / "results" / "queue_bench.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (ROOT / "docs" / "BENCHMARKS.md").write_text(
        "# Content Factory Queue Benchmarks\n\n"
        f"- **Jobs Completed:** {summary['jobs_completed']} / {summary['jobs_queued']} ({summary['completion_rate_pct']}%)\n"
        f"- **Batch Total Time:** {summary['batch_total_ms']} ms\n"
        f"- **Average Time per Job:** {summary['avg_job_ms']} ms\n",
        encoding="utf-8",
    )
    for theme in ("light", "dark"):
        (ROOT / "docs" / "img" / f"pipeline-{theme}.svg").write_text(build_pipeline_svg(theme), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
