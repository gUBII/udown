from __future__ import annotations

import json
import os
import queue
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from flask import Flask, Response, abort, render_template, request

from udown import downloader, version_formatter


def _sse(event: str, data: str) -> str:
    lines = str(data).splitlines() or [""]
    payload = "\n".join(f"data: {line}" for line in lines)
    return f"event: {event}\n{payload}\n\n"


def _queue_put(q: queue.Queue[str], message: str) -> None:
    try:
        q.put(message, timeout=0.5)
    except queue.Full:
        pass


@dataclass(frozen=True)
class Job:
    queue: queue.Queue[str]
    created_at: float


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = Job(queue=queue.Queue(maxsize=10_000), created_at=time.time())
        return job_id

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def pop(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.pop(job_id, None)


class WebProgressHook:
    def __init__(self, q: queue.Queue[str]) -> None:
        self._queue = q
        self._current_video_id: Optional[str] = None

    def __call__(self, d: dict) -> None:
        status = d.get("status")
        if status == "downloading":
            info = d.get("info_dict") or {}
            video_id = info.get("id")
            if video_id and self._current_video_id != video_id:
                self._current_video_id = video_id
                _queue_put(self._queue, _sse("new_video", info.get("title", video_id)))

            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded_bytes = d.get("downloaded_bytes") or 0
            progress = (downloaded_bytes / total_bytes) * 100 if total_bytes else 0

            progress_data = {
                "video_id": video_id,
                "progress": f"{progress:.1f}",
                "speed": d.get("_speed_str", "N/A"),
                "eta": d.get("_eta_str", "N/A"),
            }
            _queue_put(self._queue, _sse("progress", json.dumps(progress_data)))

        elif status == "finished":
            info = d.get("info_dict") or {}
            _queue_put(self._queue, _sse("message", f"Download finished: {info.get('_filename', '')}"))


def _download_task(
    q: queue.Queue[str],
    playlist_url: str,
    options: dict,
    progress_hook: WebProgressHook,
    logger: downloader.YtdlpLogger,
) -> None:
    try:
        _queue_put(q, _sse("message", "Starting download..."))
        playlist_info = downloader.download_playlist(
            playlist_url=playlist_url,
            output_dir=Path(options["output_dir"]),
            quality=options["quality"],
            name_template=options["name_template"],
            cookies_file=options.get("cookies_file"),
            log_level="info",
            save_metadata=options.get("save_metadata", False),
            progress_hook=progress_hook,
            logger=logger,
            audio_format=options.get("audio_format"),
        )
        _queue_put(q, _sse("message", f"Successfully downloaded playlist: '{playlist_info['title']}'"))
    except Exception as e:
        _queue_put(q, _sse("job_error", str(e)))
    finally:
        _queue_put(q, _sse("finished", "close"))


def create_app() -> Flask:
    app = Flask(__name__)
    jobs = JobManager()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/format")
    def format_page():
        return render_template("version_formatter.html")

    @app.post("/download")
    def start_download():
        playlist_url = request.form.get("playlist_url", "").strip()
        if not playlist_url:
            return {"error": "Playlist URL is required."}, 400

        quality = request.form.get("quality", "best")
        audio_format = None
        if "to_mp3" in request.form:
            quality = "audio-only"
            audio_format = "mp3"
        elif "audio_only" in request.form:
            quality = "audio-only"

        use_simple_serial = "simple_serial" in request.form
        name_template = (
            "{playlist_index:02d}.{ext}"
            if use_simple_serial
            else request.form.get("name_template", "{playlist_index:02d} - {title}.{ext}")
        )

        options = {
            "output_dir": request.form.get("output_dir", "./downloads"),
            "quality": quality,
            "name_template": name_template,
            "save_metadata": "save_metadata" in request.form,
            "audio_format": audio_format,
        }

        job_id = jobs.create()
        job = jobs.get(job_id)
        assert job is not None

        progress_hook = WebProgressHook(job.queue)
        web_logger = downloader.YtdlpLogger(
            warning_fn=lambda msg: _queue_put(job.queue, _sse("message", f"⚠️ WARN: {msg}")),
            error_fn=lambda msg: _queue_put(job.queue, _sse("message", f"❌ ERROR: {msg}")),
        )

        thread = threading.Thread(
            target=_download_task,
            args=(job.queue, playlist_url, options, progress_hook, web_logger),
            daemon=True,
        )
        thread.start()

        return {"job_id": job_id}

    @app.post("/format_versions")
    def format_versions():
        source_root = Path(request.form.get("source_root", "./downloads/quran_Serailler"))
        target_root = Path(request.form.get("target_root", "./downloads/quran_Serailler_serialized"))
        start_version = int(request.form.get("start_version", 1))
        end_version = int(request.form.get("end_version", 7))

        try:
            total = version_formatter.format_versions(
                source_root=source_root,
                target_root=target_root,
                start_version=start_version,
                end_version=end_version,
            )
            return {"message": f"Formatted {total} files into {target_root}"}
        except Exception as e:
            return {"error": str(e)}, 500

    @app.get("/stream/<job_id>")
    def stream(job_id: str):
        job = jobs.get(job_id)
        if not job:
            abort(404)

        def event_stream():
            try:
                while True:
                    try:
                        message = job.queue.get(timeout=15)
                    except queue.Empty:
                        yield ": keep-alive\n\n"
                        continue
                    yield message
                    if "event: finished" in message:
                        break
            finally:
                jobs.pop(job_id)

        resp = Response(event_stream(), mimetype="text/event-stream")
        resp.headers["Cache-Control"] = "no-cache"
        resp.headers["X-Accel-Buffering"] = "no"
        return resp

    return app


def main(host: Optional[str] = None, port: Optional[int] = None, debug: Optional[bool] = None) -> None:
    app = create_app()
    host = host or os.environ.get("UDOWN_HOST", "127.0.0.1")
    port = port or int(os.environ.get("UDOWN_PORT", "5000"))
    if debug is None:
        debug = os.environ.get("UDOWN_DEBUG", "").lower() in {"1", "true", "yes", "on"}
    app.run(host=host, port=port, debug=debug, threaded=True)
