from __future__ import annotations

import logging
import os
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .config import DOWNLOAD_DIR, ensure_directories, load_settings

logger = logging.getLogger("ultimate-hermes.youtube")

ALLOWED_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "music.youtube.com", "youtu.be", "www.youtube-nocookie.com", "youtube-nocookie.com"
}
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="youtube-download")
_LOCK = threading.RLock()
_JOBS: dict[str, dict[str, Any]] = {}


def _resolve_ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    common_paths = [
        Path("C:\\ffmpeg_bin\\ffmpeg.exe"),
        Path("C:\\ffmpeg\\bin\\ffmpeg.exe"),
        Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "ffmpeg" / "bin" / "ffmpeg.exe",
    ]
    for p in common_paths:
        if p.is_file():
            return str(p)
    return None


def validate_youtube_url(url: str) -> str:
    candidate = (url or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() not in ALLOWED_HOSTS:
        raise ValueError("Only public YouTube and youtu.be URLs are accepted.")
    return candidate


def _get_yt_dlp():
    try:
        import yt_dlp
        return yt_dlp
    except ImportError as exc:
        raise RuntimeError("yt-dlp is not installed. Run install.bat or: pip install -r requirements.txt") from exc


def analyze(url: str) -> dict[str, Any]:
    url = validate_youtube_url(url)
    yt_dlp = _get_yt_dlp()
    options = {
        "quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True,
        "extract_flat": False, "ignoreerrors": False, "socket_timeout": 15,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise RuntimeError("YouTube did not return video metadata.")
    
    resolutions = set()
    formats = []
    for fmt in info.get("formats", []) or []:
        height = fmt.get("height")
        if fmt.get("vcodec") not in (None, "none") and height:
            resolutions.add(int(height))
        if (fmt.get("vcodec") not in (None, "none") or fmt.get("acodec") not in (None, "none")):
            formats.append({
                "format_id": str(fmt.get("format_id", "")),
                "ext": fmt.get("ext"),
                "height": height,
                "fps": fmt.get("fps"),
                "vcodec": fmt.get("vcodec"),
                "acodec": fmt.get("acodec"),
                "filesize": fmt.get("filesize") or fmt.get("filesize_approx"),
            })
    return {
        "id": str(info.get("id", "")),
        "title": str(info.get("title", "Untitled video")),
        "uploader": str(info.get("uploader", "Unknown")),
        "duration_seconds": info.get("duration"),
        "thumbnail": info.get("thumbnail"),
        "webpage_url": info.get("webpage_url", url),
        "resolutions": sorted(resolutions, reverse=True),
        "formats": formats[:120],
        "live_status": info.get("live_status"),
        "playlist": bool(info.get("_type") == "playlist"),
    }


def _set_job(job_id: str, **fields: Any) -> None:
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id].update(fields)
            _JOBS[job_id]["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")


def start_download(url: str, quality: str = "best", output_format: str = "mp4", engine: str = "auto") -> dict[str, Any]:
    """Start an asynchronous download with dual-engine support and automatic failover."""
    settings = load_settings()
    if not settings.get("youtube_downloads_enabled", True):
        raise RuntimeError("YouTube downloads are disabled in this configuration.")
    url = validate_youtube_url(url)
    quality = str(quality or "best").lower().strip()
    output_format = str(output_format or "mp4").lower().strip()
    engine = str(engine or "auto").lower().strip()
    if quality not in {"best", "2160", "1440", "1080", "720", "480", "360"}:
        raise ValueError("Quality must be best, 2160, 1440, 1080, 720, 480, or 360.")
    if output_format not in {"mp4", "mkv", "mp3", "m4a"}:
        raise ValueError("Output format must be mp4, mkv, mp3, or m4a.")
    if engine not in {"auto", "v1", "v2"}:
        raise ValueError("Engine must be 'auto', 'v1', or 'v2'.")

    ensure_directories()
    job_id = uuid.uuid4().hex
    job = {
        "id": job_id, "url": url, "quality": quality, "format": output_format,
        "engine_requested": engine, "engine_used": None, "fallback_triggered": False,
        "status": "queued", "progress": 0.0, "speed": None, "eta_seconds": None,
        "title": None, "file_name": None, "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with _LOCK:
        _JOBS[job_id] = job
    _EXECUTOR.submit(_download_worker, job_id, url, quality, output_format, engine)
    return dict(job)


def _download_engine_v1(url: str, quality: str, output_format: str, progress_hook: Any) -> tuple[dict[str, Any], Path]:
    """Engine 1: High-fidelity DASH stream merger (bestvideo + bestaudio) with FFmpeg."""
    yt_dlp = _get_yt_dlp()
    ffmpeg_bin = _resolve_ffmpeg()
    
    cap = None if quality == "best" else int(quality)
    if output_format in {"mp3", "m4a"}:
        fmt = "bestaudio/best"
        postprocessors = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": output_format,
            "preferredquality": "192" if output_format == "mp3" else "0",
        }]
        merge_format = None
    else:
        fmt = f"bestvideo[height<={cap}]+bestaudio/best[height<={cap}]" if cap else "bestvideo+bestaudio/best"
        postprocessors = []
        merge_format = output_format

    options: dict[str, Any] = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "format": fmt,
        "outtmpl": str(DOWNLOAD_DIR / "%(title).180B [%(id)s].%(ext)s"),
        "progress_hooks": [progress_hook],
        "retries": 3, "fragment_retries": 3, "socket_timeout": 20,
        "windowsfilenames": True,
        "postprocessors": postprocessors,
    }
    if ffmpeg_bin:
        options["ffmpeg_location"] = str(Path(ffmpeg_bin).parent)
    if merge_format:
        options["merge_output_format"] = merge_format

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info:
            raise RuntimeError("Engine v1 returned no info.")
        filepath = info.get("filepath") or info.get("_filename") or ydl.prepare_filename(info)
        final_path = Path(filepath)
        if not final_path.exists():
            stem = final_path.with_suffix("")
            candidates = list(DOWNLOAD_DIR.glob(stem.name + ".*"))
            if candidates:
                final_path = max(candidates, key=lambda p: p.stat().st_mtime)
        return info, final_path


def _download_engine_v2(url: str, quality: str, output_format: str, progress_hook: Any) -> tuple[dict[str, Any], Path]:
    """Engine 2: Resilient progressive & adaptive direct stream with mobile/alternate client headers."""
    yt_dlp = _get_yt_dlp()
    ffmpeg_bin = _resolve_ffmpeg()
    
    cap = None if quality == "best" else int(quality)
    if output_format in {"mp3", "m4a"}:
        fmt = "bestaudio/best"
        postprocessors = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": output_format,
            "preferredquality": "192" if output_format == "mp3" else "0",
        }] if ffmpeg_bin else []
    else:
        fmt = f"best[height<={cap}]/bestvideo[height<={cap}]+bestaudio/best" if cap else "best/bestvideo+bestaudio"
        postprocessors = []

    options: dict[str, Any] = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "format": fmt,
        "outtmpl": str(DOWNLOAD_DIR / "%(title).180B [%(id)s]_v2.%(ext)s"),
        "progress_hooks": [progress_hook],
        "retries": 5, "fragment_retries": 5, "socket_timeout": 25,
        "windowsfilenames": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web_creator", "web"],
            }
        },
        "postprocessors": postprocessors,
    }
    if ffmpeg_bin:
        options["ffmpeg_location"] = str(Path(ffmpeg_bin).parent)

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info:
            raise RuntimeError("Engine v2 returned no info.")
        filepath = info.get("filepath") or info.get("_filename") or ydl.prepare_filename(info)
        final_path = Path(filepath)
        if not final_path.exists():
            stem = final_path.with_suffix("")
            candidates = list(DOWNLOAD_DIR.glob(stem.name + ".*"))
            if candidates:
                final_path = max(candidates, key=lambda p: p.stat().st_mtime)
        return info, final_path


def _download_worker(job_id: str, url: str, quality: str, output_format: str, engine: str) -> None:
    def progress_hook(data: dict[str, Any]) -> None:
        status = data.get("status")
        if status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            downloaded = data.get("downloaded_bytes") or 0
            progress = (float(downloaded) / float(total) * 100.0) if total else None
            speed = data.get("speed")
            eta = data.get("eta")
            fields: dict[str, Any] = {"status": "downloading", "speed": speed, "eta_seconds": eta}
            if progress is not None:
                fields["progress"] = round(min(99.9, progress), 1)
            _set_job(job_id, **fields)
        elif status == "finished":
            _set_job(job_id, status="processing", progress=99.0, speed=None, eta_seconds=None)

    # Execution strategy
    primary_engine = "v1" if engine in {"auto", "v1"} else "v2"
    secondary_engine = "v2" if primary_engine == "v1" else "v1"
    allow_fallback = (engine == "auto")

    info = None
    final_path = None
    engine_used = primary_engine
    fallback_happened = False

    try:
        if primary_engine == "v1":
            info, final_path = _download_engine_v1(url, quality, output_format, progress_hook)
        else:
            info, final_path = _download_engine_v2(url, quality, output_format, progress_hook)
    except Exception as first_exc:
        logger.warning(f"Engine {primary_engine} failed for {url}: {first_exc}")
        if allow_fallback:
            logger.info(f"Triggering automatic fallback to Engine {secondary_engine}...")
            _set_job(job_id, fallback_triggered=True, error=f"Engine {primary_engine} failed ({str(first_exc)[:150]}); switching to {secondary_engine}...")
            try:
                if secondary_engine == "v2":
                    info, final_path = _download_engine_v2(url, quality, output_format, progress_hook)
                else:
                    info, final_path = _download_engine_v1(url, quality, output_format, progress_hook)
                engine_used = secondary_engine
                fallback_happened = True
            except Exception as second_exc:
                message = f"Both engines failed. V1 error: {str(first_exc)[:200]} | V2 error: {str(second_exc)[:200]}"
                _set_job(job_id, status="failed", error=message, speed=None, eta_seconds=None)
                return
        else:
            _set_job(job_id, status="failed", error=str(first_exc)[:500], speed=None, eta_seconds=None)
            return

    if not final_path or not final_path.exists():
        # Final safety search in download dir by video ID
        vid = str(info.get("id", ""))
        candidates = sorted((p for p in DOWNLOAD_DIR.iterdir() if p.is_file() and vid and vid in p.name),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            final_path = candidates[0]
        else:
            _set_job(job_id, status="failed", error="Download completed but final output file was not found.")
            return

    _set_job(
        job_id,
        status="completed",
        progress=100.0,
        title=info.get("title"),
        file_name=final_path.name,
        output_path=str(final_path),
        engine_used=engine_used,
        fallback_triggered=fallback_happened,
        speed=None,
        eta_seconds=0,
        error=None,
    )


def get_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def list_downloads() -> list[dict[str, Any]]:
    ensure_directories()
    results = []
    for path in sorted(DOWNLOAD_DIR.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if path.is_file():
            results.append({
                "file_name": path.name,
                "size_bytes": path.stat().st_size,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            })
    return results[:100]


def resolve_download(file_name: str) -> Path:
    if not file_name or Path(file_name).name != file_name or file_name in {".", ".."}:
        raise ValueError("Invalid filename.")
    path = (DOWNLOAD_DIR / file_name).resolve()
    if path.parent != DOWNLOAD_DIR.resolve() or not path.is_file():
        raise FileNotFoundError("Downloaded file not found.")
    return path
