from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.staticfiles import StaticFiles

from ultimate_agent.agent import agent, emergency_stop, reset_stop, stop_is_set
from ultimate_agent.config import AVAILABLE_GEMINI_MODELS, ROOT, load_settings, public_settings, save_settings
from ultimate_agent.file_memory import file_memory
from ultimate_agent.folder_tools import analyze_document, create_folder, list_directory
from ultimate_agent.keyring import AllGeminiKeysFailed, NoGeminiKeys
from ultimate_agent.mcp_bridge import mcp_bridge
from ultimate_agent.store import store
from ultimate_agent.tools import LOCAL_TOOLS, execute_local_tool, list_skills, registry
from ultimate_agent.youtube import analyze as youtube_analyze, get_job, list_downloads, resolve_download, start_download

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ultimate-hermes")

app = FastAPI(title="Ultimate Hermes Agent Hub", version="1.0.0", docs_url="/api/docs", redoc_url=None)
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=16000)


class IndexRequest(BaseModel):
    path: str = Field(min_length=1, max_length=2000)
    recursive: bool = True
    force: bool = False


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=8, ge=1, le=20)


class ArchiveRequest(BaseModel):
    path: str = Field(min_length=1, max_length=2000)


class AnalyzeRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


class DownloadRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    quality: str = "best"
    output_format: str = "mp4"
    engine: str = "auto"


class FolderCreateRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1000)


class FolderListRequest(BaseModel):
    path: str = ""
    sort_by: str = "name"
    reverse: bool = False


class DocAnalyzeRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1000)


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    confirm: bool = False


class SettingsRequest(BaseModel):
    gemini_model: str = "gemini-3.5-flash"
    gemini_api_keys_text: str = ""
    mcp_servers_json: str = "[]"


class ModelUpdateRequest(BaseModel):
    model: str


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    mcp_status = mcp_bridge.status()
    settings = public_settings()
    return {"ok": True, "app": "Ultimate Hermes Agent Hub", "version": "1.0.0",
            "gemini_key_count": settings["gemini_key_count"], "gemini_model": settings["gemini_model"],
            "file_memory": file_memory.stats(), "mcp_tool_count": mcp_status["tool_count"],
            "emergency_stop": stop_is_set()}


@app.get("/api/state")
def state() -> dict[str, Any]:
    result = health()
    result["messages"] = store.recent_messages(80)
    result["pending_approvals"] = store.pending_approvals()
    result["downloads"] = list_downloads()[:12]
    result["mcp"] = mcp_bridge.status()
    result["skills"] = list_skills()
    result["settings"] = public_settings()
    return result


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    if stop_is_set():
        raise HTTPException(status_code=423, detail="Emergency stop is active. Reset it in the dashboard before sending a new task.")
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message cannot be blank.")
    history = store.history(limit=int(load_settings().get("history_limit", 12)))
    store.add_message("user", message)
    try:
        result = agent.chat(message, history=history)
        response_text = str(result.get("response", "No response received."))
        store.add_message("assistant", response_text)
        return {**result, "history": store.recent_messages(80)}
    except NoGeminiKeys as exc:
        store.add_message("assistant", str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AllGeminiKeysFailed as exc:
        safe_message = str(exc)
        store.add_message("assistant", safe_message)
        raise HTTPException(status_code=502, detail=safe_message) from exc
    except Exception as exc:
        logger.exception("Chat request failed")
        safe_message = f"Chat failed ({type(exc).__name__}). Check Settings, the selected Gemini model, and the local logs."
        store.add_message("assistant", safe_message)
        raise HTTPException(status_code=502, detail=safe_message) from exc


@app.post("/api/chat/clear")
def clear_chat() -> dict[str, str]:
    store.clear_messages()
    return {"status": "cleared"}


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return public_settings()


@app.get("/api/settings/configuration")
def get_safe_configuration() -> dict[str, Any]:
    settings = load_settings()
    visible_servers = []
    for server in settings.get("mcp_servers", []):
        if not isinstance(server, dict):
            continue
        safe = {k: v for k, v in server.items() if k != "env"}
        # Never send environment variable values (they may contain server credentials) to the browser.
        if isinstance(server.get("env"), dict) and server["env"]:
            safe["env_configured_keys"] = sorted(str(k) for k in server["env"].keys())
        visible_servers.append(safe)
    return {"mcp_servers": visible_servers}


@app.post("/api/settings")
def post_settings(request: SettingsRequest) -> dict[str, Any]:
    import re
    # If the user left the keys input blank, keep their existing saved keys.
    # If they supplied text, parse and update the keys.
    raw_keys_text = request.gemini_api_keys_text.strip()
    if raw_keys_text:
        keys = [part.strip() for part in re.split(r"[,;\r\n]+", raw_keys_text) if part.strip()]
    else:
        keys = None

    try:
        mcp_servers = json.loads(request.mcp_servers_json or "[]")
        if not isinstance(mcp_servers, list):
            raise ValueError("MCP server configuration must be a JSON array.")
        previous = load_settings().get("mcp_servers", [])
        previous_by_name = {str(item.get("name")): item for item in previous if isinstance(item, dict)}
        for server in mcp_servers:
            if not isinstance(server, dict):
                raise ValueError("Each MCP server must be a JSON object.")
            old_server = previous_by_name.get(str(server.get("name", "")), {})
            # This UI-only marker is generated by the redacted GET endpoint; never persist it.
            server.pop("env_configured_keys", None)
            if "env" not in server and isinstance(old_server.get("env"), dict):
                server["env"] = old_server["env"]
            if server.get("transport", "stdio") == "stdio":
                if server.get("enabled") and (not isinstance(server.get("command"), str) or not server.get("command")):
                    raise ValueError("An enabled stdio MCP server needs a command.")
                if not isinstance(server.get("args", []), list):
                    raise ValueError("MCP server args must be a JSON array.")
        save_settings(gemini_api_keys=keys, gemini_model=request.gemini_model, mcp_servers=mcp_servers)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # Invalidate cached tool schemas; keys are fetched fresh for every generation.
    mcp_bridge._cache_at = 0
    return {"status": "saved", **public_settings(),
            "warning": "Keys are stored locally in data/local_settings.json. Environment keys remain active in addition to these keys."}


@app.post("/api/settings/model")
def update_model(request: ModelUpdateRequest) -> dict[str, Any]:
    model = request.model.strip()
    if not model:
        raise HTTPException(status_code=422, detail="Model ID cannot be blank.")
    save_settings(gemini_api_keys=None, gemini_model=model)
    return {"status": "updated", **public_settings()}


@app.post("/api/settings/keys/clear")
def clear_keys() -> dict[str, Any]:
    current_model = load_settings().get("gemini_model", "gemini-3.5-flash")
    save_settings(gemini_api_keys=[], gemini_model=current_model)
    return {"status": "cleared", **public_settings()}


@app.post("/api/files/index")
def index_folder(request: IndexRequest) -> dict[str, Any]:
    try:
        return file_memory.index_folder(request.path, request.recursive, request.force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/files/search")
def search_files(request: SearchRequest) -> dict[str, Any]:
    return {"query": request.query, "results": file_memory.search(request.query, request.limit),
            "stats": file_memory.stats()}


@app.post("/api/archives/analyze")
def analyze_archive(request: ArchiveRequest) -> dict[str, Any]:
    try:
        return file_memory.analyze_archive(request.path)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not inspect archive ({type(exc).__name__}).") from exc


@app.get("/api/files/stats")
def file_stats() -> dict[str, int]:
    return file_memory.stats()


@app.post("/api/youtube/analyze")
def analyze_video(request: AnalyzeRequest) -> dict[str, Any]:
    try:
        return youtube_analyze(request.url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not analyze video: {str(exc)[:700]}") from exc


@app.post("/api/youtube/download")
def download_video(request: DownloadRequest) -> dict[str, Any]:
    try:
        return start_download(request.url, request.quality, request.output_format, request.engine)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)[:700]) from exc


@app.get("/api/models")
def get_available_models() -> dict[str, Any]:
    return {"models": AVAILABLE_GEMINI_MODELS}


@app.post("/api/folder/create")
def api_create_folder(request: FolderCreateRequest) -> dict[str, Any]:
    try:
        return create_folder(request.path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/folder/list")
def api_list_folder(request: FolderListRequest) -> dict[str, Any]:
    try:
        return list_directory(request.path, request.sort_by, request.reverse)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/document/analyze")
def api_analyze_doc(request: DocAnalyzeRequest) -> dict[str, Any]:
    try:
        return analyze_document(request.path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/youtube/jobs/{job_id}")
def youtube_job(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Download job not found.")
    # Do not expose absolute filesystem paths to the browser.
    job.pop("output_path", None)
    return job


@app.get("/api/youtube/files")
def youtube_files() -> dict[str, Any]:
    return {"files": list_downloads()}


@app.get("/api/youtube/files/{file_name:path}")
def download_file(file_name: str) -> FileResponse:
    try:
        path = resolve_download(file_name)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, filename=path.name, content_disposition_type="attachment")


@app.get("/api/tools")
def tools_list() -> dict[str, Any]:
    tools = registry.definitions(include_mcp=True)
    return {"tools": [{"name": item["name"], "description": item.get("description", ""),
                        "schema": item.get("input_schema", item.get("schema", {})),
                        "requires_approval": item.get("requires_approval", False)} for item in tools]}


@app.post("/api/tools/call")
def call_tool(request: ToolCallRequest) -> dict[str, Any]:
    result = registry.call(request.name, request.arguments)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Tool failed"))
    return result


@app.get("/api/mcp/status")
def mcp_status() -> dict[str, Any]:
    return mcp_bridge.status()


@app.post("/api/mcp/refresh")
def refresh_mcp() -> dict[str, Any]:
    tools = mcp_bridge.list_tools(force=True)
    status = mcp_bridge.status()
    return {"tools": [{k: v for k, v in item.items() if k != "input_schema"} for item in tools], **status}


@app.post("/api/approvals/{approval_id}/approve")
def approve_tool(approval_id: str, request: ApprovalRequest) -> dict[str, Any]:
    if not request.confirm:
        raise HTTPException(status_code=400, detail="Explicit confirmation is required.")
    if stop_is_set():
        raise HTTPException(status_code=423, detail="Emergency stop is active; pending Windows actions cannot run.")
    approval = store.approval(approval_id)
    if not approval or approval["status"] != "pending":
        raise HTTPException(status_code=404, detail="Pending approval was not found.")
    try:
        result = mcp_bridge.call_tool(approval["server_name"], approval["tool_name"], approval["arguments"])
        status = "failed" if result.get("is_error") else "approved"
        store.finish_approval(approval_id, status, result)
        summary = f"Windows tool `{approval['display_name']}` {status}. Result: {json.dumps(result, ensure_ascii=False)[:7000]}"
        store.add_message("assistant", summary)
        return {"status": status, "result": result, "history": store.recent_messages(80)}
    except Exception as exc:
        result = {"error": f"{type(exc).__name__}: {str(exc)[:600]}"}
        store.finish_approval(approval_id, "failed", result)
        raise HTTPException(status_code=502, detail=result["error"]) from exc


@app.post("/api/approvals/{approval_id}/deny")
def deny_tool(approval_id: str) -> dict[str, str]:
    approval = store.approval(approval_id)
    if not approval or approval["status"] != "pending":
        raise HTTPException(status_code=404, detail="Pending approval was not found.")
    store.finish_approval(approval_id, "denied", {"message": "Denied by the user."})
    store.add_message("assistant", f"Windows action `{approval['display_name']}` was denied; it was not run.")
    return {"status": "denied"}


@app.get("/api/approvals")
def pending_approvals() -> dict[str, Any]:
    return {"pending": store.pending_approvals(), "emergency_stop": stop_is_set()}


@app.post("/api/emergency-stop")
def activate_emergency_stop() -> dict[str, Any]:
    emergency_stop()
    return {"status": "stopped", "message": "New tool actions and pending Windows approvals are blocked."}


@app.post("/api/emergency-stop/reset")
def reset_emergency_stop_endpoint() -> dict[str, Any]:
    reset_stop()
    return {"status": "reset", "message": "Emergency stop is reset."}


@app.get("/api/skills")
def skills_list(query: str = "", limit: int = 100) -> dict[str, Any]:
    return {"skills": list_skills(query, limit), "total_matching": len(list_skills(query, 250))}


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("APP_HOST", "127.0.0.1")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        logger.warning("Binding beyond loopback is unsafe without adding authentication. Forcing 127.0.0.1.")
        host = "127.0.0.1"
    uvicorn.run(app, host=host, port=int(os.getenv("APP_PORT", "8765")), log_level="info")
