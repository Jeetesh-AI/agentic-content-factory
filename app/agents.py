"""Multi-agent video production pipeline: Script -> Narration -> Visuals -> Cut."""

import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import time
from typing import Any, Dict, List, Optional
import wave

from app.queue import JobQueue


def _write_tone_wav(path: Path, duration_s: float = 1.5, freq_hz: float = 220.0) -> None:
    sample_rate = 16000
    n_samples = int(sample_rate * duration_s)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            val = int(8000 * math.sin(2.0 * math.pi * freq_hz * (i / sample_rate)))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(bytes(frames))


class ContentPipelineWorker:
    """Executes queued video jobs across 4 deterministic/pluggable agent stages."""

    def __init__(self, queue: JobQueue, output_root: Path) -> None:
        self.queue = queue
        self.output_root = output_root
        self.output_root.mkdir(parents=True, exist_ok=True)

    def _script_agent(self, topic: str) -> List[Dict[str, str]]:
        return [
            {"scene": 1, "narration": f"Hook: Why {topic} matters right now.", "visual": "Bold kinetic title card"},
            {"scene": 2, "narration": f"Core insight on {topic} in 10 seconds.", "visual": "Clean architecture breakdown"},
            {"scene": 3, "narration": "Takeaway: Measure everything you ship.", "visual": "End card & call to action"},
        ]

    def _narration_agent(self, job_dir: Path, scenes: List[Dict[str, str]]) -> Path:
        wav_path = job_dir / "narration.wav"
        _write_tone_wav(wav_path, duration_s=1.2)
        return wav_path

    def _visuals_agent(self, job_dir: Path, scenes: List[Dict[str, str]]) -> List[Path]:
        frames: List[Path] = []
        for s in scenes:
            svg_path = job_dir / f"scene_{s['scene']}.svg"
            svg_path.write_text(
                f'<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920">'
                f'<rect width="1080" height="1920" fill="#0d1117"/>'
                f'<text x="540" y="920" text-anchor="middle" fill="#a78bfa" font-size="48" font-family="sans-serif">Scene {s["scene"]}</text>'
                f'<text x="540" y="1000" text-anchor="middle" fill="#e6edf3" font-size="32" font-family="sans-serif">{s["visual"]}</text>'
                f"</svg>",
                encoding="utf-8",
            )
            frames.append(svg_path)
        return frames

    def _cut_agent(self, job_dir: Path, scenes: List[Dict[str, str]], wav_path: Path, frames: List[Path]) -> Path:
        manifest_path = job_dir / "render_manifest.json"
        video_path = job_dir / "output_vertical.mp4"
        ffmpeg_bin = shutil.which("ffmpeg")
        rendered_mp4 = False

        if ffmpeg_bin:
            cmd = [
                ffmpeg_bin, "-y",
                "-f", "lavfi", "-i", "color=c=#0d1117:s=720x1280:d=1.2",
                "-i", str(wav_path),
                "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                str(video_path),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            rendered_mp4 = proc.returncode == 0 and video_path.exists()

        manifest_path.write_text(
            json.dumps(
                {
                    "format": "9:16 vertical",
                    "scenes": scenes,
                    "audio": wav_path.name,
                    "frames": [f.name for f in frames],
                    "mp4_rendered": rendered_mp4,
                    "video_file": video_path.name if rendered_mp4 else None,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return video_path if rendered_mp4 else manifest_path

    def process_next(self) -> Optional[Dict[str, Any]]:
        job = self.queue.claim_next()
        if not job:
            return None

        job_id = job["id"]
        job_dir = self.output_root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        timings: Dict[str, float] = {}

        try:
            t0 = time.perf_counter()
            scenes = self._script_agent(job["topic"])
            timings["script_ms"] = round((time.perf_counter() - t0) * 1000, 2)

            self.queue.update_stage(job_id, "narrating")
            t1 = time.perf_counter()
            wav_path = self._narration_agent(job_dir, scenes)
            timings["narration_ms"] = round((time.perf_counter() - t1) * 1000, 2)

            self.queue.update_stage(job_id, "visuals")
            t2 = time.perf_counter()
            frames = self._visuals_agent(job_dir, scenes)
            timings["visuals_ms"] = round((time.perf_counter() - t2) * 1000, 2)

            self.queue.update_stage(job_id, "cutting")
            t3 = time.perf_counter()
            artifact = self._cut_agent(job_dir, scenes, wav_path, frames)
            timings["cut_ms"] = round((time.perf_counter() - t3) * 1000, 2)

            self.queue.complete(job_id, str(artifact), timings)
            return self.queue.get(job_id)
        except Exception as exc:
            self.queue.fail(job_id, str(exc))
            return self.queue.get(job_id)
