from __future__ import annotations

import json
import os
import re
from pathlib import Path
from threading import RLock
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOWNLOAD_DIR = DATA_DIR / "downloads"
WORKSPACE_DIR = ROOT / "workspace"
SETTINGS_PATH = DATA_DIR / "local_settings.json"
DATABASE_PATH = DATA_DIR / "app.sqlite3"
MEMORY_DATABASE_PATH = DATA_DIR / "file_memory.sqlite3"
SETTINGS_LOCK = RLock()

DEFAULT_SETTINGS: dict[str, Any] = {
    "gemini_model": "gemini-flash-lite-latest",
    "gemini_api_keys": [],
    "mcp_servers": [],
    "history_limit": 12,
    "youtube_downloads_enabled": True,
}

AVAILABLE_GEMINI_MODELS: list[dict[str, str]] = [
    {"id": "gemini-flash-lite-latest", "label": "Gemini Flash Lite Latest (Recommended)", "description": "Ultra fast, high availability"},
    {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash Lite", "description": "Fast & responsive multi-modal"},
    {"id": "gemini-3.8-flash", "label": "Gemini 3.8 Flash", "description": "Latest Gemini 3.8 release"},
    {"id": "gemini-3.1-pro-preview", "label": "Gemini 3.1 Pro Preview", "description": "Advanced reasoning & coding"},
    {"id": "gemini-flash-latest", "label": "Gemini Flash Latest", "description": "General purpose flash"},
    {"id": "gemini-pro-latest", "label": "Gemini Pro Latest", "description": "General purpose pro"},
]


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def load_settings() -> dict[str, Any]:
    ensure_directories()
    with SETTINGS_LOCK:
        saved = _read_json(SETTINGS_PATH, {})
    result = dict(DEFAULT_SETTINGS)
    if isinstance(saved, dict):
        result.update(saved)
    # Use the environment variable only as a fallback when no model was
    # explicitly saved by the user via the dashboard.
    if not isinstance(saved, dict) or "gemini_model" not in saved:
        model = os.getenv("GEMINI_MODEL")
        if model:
            result["gemini_model"] = model.strip()
    if not isinstance(result.get("gemini_api_keys"), list):
        result["gemini_api_keys"] = []
    if not isinstance(result.get("mcp_servers"), list):
        result["mcp_servers"] = []
    return result


def _split_keys(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r"[,;\r\n]+", value) if item.strip()]


def get_gemini_keys() -> list[str]:
    settings = load_settings()
    values = list(settings.get("gemini_api_keys", []))
    values.extend(_split_keys(os.getenv("GEMINI_API_KEYS")))
    values.extend(_split_keys(os.getenv("GEMINI_API_KEY")))
    values.extend(_split_keys(os.getenv("GOOGLE_API_KEY")))
    # Preserve order while deduplicating. Never write env keys back into settings.
    return list(dict.fromkeys(str(v).strip() for v in values if str(v).strip()))


def save_settings(*, gemini_api_keys: list[str] | None = None, gemini_model: str,
                  mcp_servers: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    ensure_directories()
    current = load_settings()
    if gemini_api_keys is None:
        keys = list(current.get("gemini_api_keys", []))
    else:
        keys = list(dict.fromkeys(str(v).strip() for v in gemini_api_keys if str(v).strip()))
    if not gemini_model.strip():
        raise ValueError("Gemini model cannot be empty.")
    if len(keys) > 30:
        raise ValueError("At most 30 Gemini keys may be configured.")
    servers = mcp_servers if mcp_servers is not None else current.get("mcp_servers", [])
    if not isinstance(servers, list):
        raise ValueError("mcp_servers must be a JSON list.")
    payload = {
        "gemini_model": gemini_model.strip(),
        "gemini_api_keys": keys,
        "mcp_servers": servers,
        "history_limit": int(current.get("history_limit", 12)),
        "youtube_downloads_enabled": bool(current.get("youtube_downloads_enabled", True)),
    }
    with SETTINGS_LOCK:
        SETTINGS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    # Best-effort restrictive permissions on POSIX; Windows uses the current user's profile ACL.
    try:
        SETTINGS_PATH.chmod(0o600)
    except OSError:
        pass
    return payload


def public_settings() -> dict[str, Any]:
    settings = load_settings()
    env_keys = (_split_keys(os.getenv("GEMINI_API_KEYS")) + _split_keys(os.getenv("GEMINI_API_KEY"))
                + _split_keys(os.getenv("GOOGLE_API_KEY")))
    key_count = len(list(dict.fromkeys([*settings.get("gemini_api_keys", []), *env_keys])))
    return {
        "gemini_model": settings.get("gemini_model", DEFAULT_SETTINGS["gemini_model"]),
        "gemini_key_count": key_count,
        "saved_key_count": len(settings.get("gemini_api_keys", [])),
        "gemini_api_keys": settings.get("gemini_api_keys", []),
        "available_models": AVAILABLE_GEMINI_MODELS,
        "mcp_servers": [
            {"name": s.get("name", f"server-{i+1}"), "transport": s.get("transport", "stdio"),
             "enabled": bool(s.get("enabled", False)), "command": s.get("command", "")}
            for i, s in enumerate(settings.get("mcp_servers", [])) if isinstance(s, dict)
        ],
        "settings_file": str(SETTINGS_PATH),
    }
