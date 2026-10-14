from __future__ import annotations

import json
import logging
import threading
from typing import Any

from .config import load_settings
from .keyring import key_pool
from .tools import registry

logger = logging.getLogger("ultimate-hermes.agent")

SYSTEM_INSTRUCTION = """You are Ultimate Hermes Agent, a unified, local-first AI assistant equipped with all tools, skills, and features from the user's environment.

Your capabilities include:
1. Files, Folders & Programs:
   - Create directories anywhere (create_folder): workspace, Desktop, Documents, or custom paths.
   - Create program files, document shells, and scripts with content (create_file, write_file).
   - Read and inspect files line-by-line (read_file).
   - Edit files with precise replacements (edit_file).
   - Move, copy, rename, delete files/folders (move_item, copy_item, rename_item, delete_item).
   - Compress files and folders into .zip or .tar (compress_item).
   - List and sort folder contents by size, date, name, or type (list_directory).
   - Deeply analyze documents: .docx, .pdf, .pptx, .xlsx, .csv, and source code (analyze_document).

2. Dual-Engine YouTube Downloader:
   - Analyze video formats and resolutions (youtube_analyze).
   - Download video/audio with automatic dual-engine failover (youtube_download). Engine 1 uses high-definition DASH merging; Engine 2 uses resilient progressive/direct streaming. If one engine fails, the other automatically takes over.

3. Shell Execution & Live Web:
   - Run PowerShell/CMD commands in the workspace (run_command).
   - Search the web for live information with sources (web_search).
   - Fetch and extract web page content (web_fetch).

4. Windows Desktop Automation:
   - View open windows (windows_list_windows).
   - Monitor active processes (windows_list_processes).
   - Capture desktop screenshots (windows_take_screenshot).
   - Read/write system clipboard (windows_clipboard_get, windows_clipboard_set).
   - Launch Windows applications (windows_open_app).

5. Skills Library & Persistent Memory:
   - Browse the 58 bundled Hermes skills (list_agent_skills) and read their complete workflow specifications (read_skill).
   - Index folders into persistent SQLite FTS5 search (file_index_folder, file_search).
   - Inspect ZIP archives safely without extraction (zip_archive_inventory).

Always take direct action by calling the appropriate tool when asked to do something (e.g. create a folder, create a file, download a video, analyze a doc). Report actual tool results clearly."""

_STOP_EVENT = threading.Event()


def emergency_stop() -> None:
    _STOP_EVENT.set()


def reset_stop() -> None:
    _STOP_EVENT.clear()


def stop_is_set() -> bool:
    return _STOP_EVENT.is_set()


def _safe_schema(schema: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(schema, dict) or schema.get("type", "object") != "object":
        return {"type": "object", "properties": {}}
    forbidden = {"$schema", "$defs", "definitions", "title", "examples", "default", "additionalProperties"}

    def clean(node: Any, depth: int = 0) -> Any:
        if depth > 8:
            return {"type": "string", "description": "Nested schema omitted due to depth."}
        if isinstance(node, dict):
            return {k: clean(v, depth + 1) for k, v in node.items() if k not in forbidden}
        if isinstance(node, list):
            return [clean(v, depth + 1) for v in node[:40]]
        return node

    result = clean(schema)
    if not isinstance(result.get("properties"), dict):
        result["properties"] = {}
    result["type"] = "object"
    result.pop("required", None) if not isinstance(result.get("required"), list) else None
    result["properties"] = dict(list(result["properties"].items())[:80])
    return result


def _extract_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    chunks = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            value = getattr(part, "text", None)
            if value:
                chunks.append(str(value))
    return "\n".join(chunks).strip()


class UltimateAgent:
    def __init__(self) -> None:
        self._client_cache: dict[str, Any] = {}
        self._cache_lock = threading.Lock()

    def _generate(self, *, requested_model: str, contents: list[Any], config: Any) -> Any:
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("Google Gen AI SDK is missing. Run install.bat or pip install -r requirements.txt.") from exc

        # Construct multi-model fallback chain to ensure maximum resilience
        candidate_models = [requested_model, "gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.8-flash"]
        # Deduplicate preserving order
        candidate_models = list(dict.fromkeys(m for m in candidate_models if m))

        last_error = None
        for model in candidate_models:
            def operation(api_key: str):
                with self._cache_lock:
                    client = self._client_cache.get(api_key)
                    if client is None:
                        client = genai.Client(api_key=api_key, http_options={"timeout": 60_000})
                        if len(self._client_cache) >= 12:
                            self._client_cache.clear()
                        self._client_cache[api_key] = client
                return client.models.generate_content(model=model, contents=contents, config=config)

            try:
                return key_pool.call(operation)
            except Exception as exc:
                last_error = exc
                err_str = str(exc).lower()
                # If model is 503 high demand, 429 quota, or 404 not found, try next candidate model
                if any(k in err_str for k in ["503", "429", "404", "quota", "demand", "not found", "unavailable"]):
                    logger.warning(f"Model {model} failed ({exc}); attempting fallback to next model in chain...")
                    continue
                # Other non-model errors: reraise
                raise

        raise last_error

    def chat(self, message: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        try:
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("Google Gen AI SDK is missing. Run install.bat or pip install -r requirements.txt.") from exc

        settings = load_settings()
        requested_model = str(settings.get("gemini_model") or "gemini-flash-lite-latest")
        definitions = registry.definitions(include_mcp=True)
        declarations = []
        for spec in definitions[:80]:
            try:
                declarations.append(types.FunctionDeclaration(
                    name=spec["name"],
                    description=str(spec.get("description", ""))[:1000],
                    parameters_json_schema=_safe_schema(spec.get("input_schema") or spec.get("schema") or {"type": "object", "properties": {}}),
                ))
            except Exception:
                continue

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[types.Tool(function_declarations=declarations)] if declarations else None,
            temperature=0.35,
            max_output_tokens=4096,
        )

        contents: list[Any] = []
        for item in (history or [])[-24:]:
            role = "model" if item.get("role") == "assistant" else "user"
            text = str(item.get("content", ""))[:12000]
            if text:
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message[:16000])]))

        pending_approvals: list[dict[str, Any]] = []
        calls_made = 0

        for _ in range(8):
            if stop_is_set():
                return {
                    "response": "Emergency stop is active. Reset it before running another tool action.",
                    "pending_approvals": pending_approvals,
                    "tool_calls": calls_made,
                    "stopped": True,
                }

            response = self._generate(requested_model=requested_model, contents=contents, config=config)
            candidate = (getattr(response, "candidates", None) or [None])[0]
            content = getattr(candidate, "content", None) if candidate else None
            if content is not None:
                contents.append(content)

            parts = getattr(content, "parts", []) or []
            function_calls = [getattr(part, "function_call", None) for part in parts]
            function_calls = [call for call in function_calls if call is not None and getattr(call, "name", None)]
            if not function_calls:
                final_text = _extract_text(response) or "The model completed the request."
                return {
                    "response": final_text,
                    "pending_approvals": pending_approvals,
                    "tool_calls": calls_made,
                    "stopped": False,
                }

            function_responses = []
            for function_call in function_calls[:8]:
                if stop_is_set():
                    break
                tool_name = str(function_call.name)
                args = getattr(function_call, "args", {}) or {}
                if not isinstance(args, dict):
                    args = {}
                calls_made += 1
                try:
                    result = registry.call(tool_name, args)
                except Exception as exc:
                    result = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}

                if result.get("approval_required"):
                    pending_approvals.append({
                        "id": result["approval_id"],
                        "tool": tool_name,
                        "arguments": args,
                        "status": "pending",
                    })
                    return {
                        "response": f"I requested Windows action `{tool_name}`. It requires your approval in the Windows Tools panel before it can run.",
                        "pending_approvals": pending_approvals,
                        "tool_calls": calls_made,
                        "stopped": False,
                    }

                response_payload = json.loads(json.dumps(result, ensure_ascii=False, default=str))
                response_payload = {"result": response_payload}
                function_responses.append(types.Part.from_function_response(name=tool_name, response=response_payload))

            if function_responses:
                contents.append(types.Content(role="user", parts=function_responses))
            elif stop_is_set():
                return {
                    "response": "Stopped before executing the next tool call.",
                    "pending_approvals": pending_approvals,
                    "tool_calls": calls_made,
                    "stopped": True,
                }

        return {
            "response": "Tool execution sequence completed. The tools returned their results above.",
            "pending_approvals": pending_approvals,
            "tool_calls": calls_made,
            "stopped": False,
        }


agent = UltimateAgent()
