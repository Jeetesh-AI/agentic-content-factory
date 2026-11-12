# Agentic Content Factory

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite Queue](https://img.shields.io/badge/Queue-SQLite%20Persistent-22C55E)](app/queue.py)

**Unattended multi-agent pipeline that turns a story idea into a vertical 9:16 video package — script, WAV narration, vertical scene frames, and FFmpeg cut/manifest — across a persistent SQLite job queue.**

<p align="center">
  <img src="docs/media/demo.gif" width="540" alt="Three vertical 9:16 video packages generated across the pipeline" />
</p>

| **5 / 5** | **100%** | **5.2 ms** | **4** |
| :---: | :---: | :---: | :---: |
| queued jobs completed in batch run | end-to-end completion rate | average job orchestration time (without FFmpeg transcode) | isolated agent stages (`Script → Narration → Visuals → Cut`) |

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/pipeline-dark.svg">
  <img alt="Multi-agent pipeline: SQLite Job Queue -> Script Agent -> Narration -> Visuals -> Cut Agent" src="docs/img/pipeline-light.svg">
</picture>

Full batch metrics: **[docs/BENCHMARKS.md](docs/BENCHMARKS.md)**.

---

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

pytest -v
python scripts/bench_queue.py
uvicorn app.main:app --port 8000
```
