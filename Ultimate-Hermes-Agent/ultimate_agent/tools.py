from __future__ import annotations

import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ROOT, WORKSPACE_DIR
from .file_memory import file_memory
from .folder_tools import (
    analyze_document,
    compress_item,
    copy_item,
    create_file,
    create_folder,
    delete_item,
    edit_file,
    list_directory,
    move_item,
    read_file,
    rename_item,
    write_file,
)
from .mcp_bridge import mcp_bridge
from .store import store
from .system_tools import (
    read_skill,
    run_command,
    web_fetch,
    web_search,
    windows_clipboard_get,
    windows_clipboard_set,
    windows_list_processes,
    windows_list_windows,
    windows_open_app,
    windows_take_screenshot,
)
from .youtube import analyze as youtube_analyze, start_download as youtube_download


LOCAL_TOOLS: list[dict[str, Any]] = [
    # --- File & Folder Tools (from analysis_of_files & Parity Workbench) ---
    {
        "name": "create_folder",
        "description": "Create a new folder or directory. Can be in workspace, Desktop, Documents, or any relative/absolute path.",
        "schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Folder path to create, e.g. 'MyProgram', 'Desktop/Notes'"}},
            "required": ["path"],
        },
    },
    {
        "name": "create_file",
        "description": "Create a new document, program file, or script with content. Fails if file already exists.",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path, e.g. 'MyProgram/script.py' or 'notes.txt'"},
                "content": {"type": "string", "description": "Text or code content of the file"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "Read text or code from an existing file with line numbers.",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"},
                "start_line": {"type": "integer", "description": "1-based starting line number (default 1)"},
                "end_line": {"type": "integer", "description": "Ending line number"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write or overwrite content to a file.",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write to"},
                "content": {"type": "string", "description": "Text or code content"},
                "overwrite": {"type": "boolean", "description": "Whether to overwrite existing file (default true)"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace a unique string snippet in an existing file.",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to edit"},
                "old_text": {"type": "string", "description": "Exact text snippet to replace"},
                "new_text": {"type": "string", "description": "New replacement text"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "move_item",
        "description": "Move a file or folder from source to destination.",
        "schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source path"},
                "destination": {"type": "string", "description": "Destination path"},
            },
            "required": ["source", "destination"],
        },
    },
    {
        "name": "copy_item",
        "description": "Copy a file or folder from source to destination.",
        "schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source path"},
                "destination": {"type": "string", "description": "Destination path"},
            },
            "required": ["source", "destination"],
        },
    },
    {
        "name": "rename_item",
        "description": "Rename a file or folder.",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to rename"},
                "new_name": {"type": "string", "description": "New name (not full path)"},
            },
            "required": ["path", "new_name"],
        },
    },
    {
        "name": "delete_item",
        "description": "Delete a file or folder (system directories are protected).",
        "schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path to delete"}},
            "required": ["path"],
        },
    },
    {
        "name": "compress_item",
        "description": "Compress a file or directory into a .zip or .tar archive.",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to compress"},
                "format": {"type": "string", "enum": ["zip", "tar"], "description": "Archive format (default zip)"},
                "destination": {"type": "string", "description": "Optional destination folder"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_directory",
        "description": "List directory contents with file size, modified date, and sorting options.",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (defaults to workspace)"},
                "sort_by": {"type": "string", "enum": ["name", "size", "date", "type"], "description": "Sort criterion"},
                "reverse": {"type": "boolean", "description": "Sort descending"},
            },
        },
    },
    {
        "name": "analyze_document",
        "description": "Extract structured text and summary from Word (.docx), PDF (.pdf), PowerPoint (.pptx), Excel (.xlsx), CSV, and code files.",
        "schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Document path to analyze"}},
            "required": ["path"],
        },
    },

    # --- YouTube Downloader (Dual-Engine with Fallback) ---
    {
        "name": "youtube_analyze",
        "description": "Inspect public YouTube video metadata and available resolutions.",
        "schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "Public YouTube video URL"}},
            "required": ["url"],
        },
    },
    {
        "name": "youtube_download",
        "description": "Download a YouTube video with dual-engine failover. Engine 1 is high-definition DASH with ffmpeg; Engine 2 is resilient progressive stream. If Engine 1 fails, Engine 2 automatically takes over.",
        "schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "YouTube URL"},
                "quality": {"type": "string", "enum": ["best", "2160", "1440", "1080", "720", "480", "360"]},
                "output_format": {"type": "string", "enum": ["mp4", "mkv", "mp3", "m4a"]},
                "engine": {"type": "string", "enum": ["auto", "v1", "v2"], "description": "Download engine: 'auto' (v1 with automatic v2 failover), 'v1', or 'v2'"},
            },
            "required": ["url"],
        },
    },

    # --- Shell Execution & Web Tools ---
    {
        "name": "run_command",
        "description": "Execute a PowerShell or CMD command in the workspace directory and return the output.",
        "schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout_seconds": {"type": "integer", "description": "Timeout in seconds (default 60)"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "web_search",
        "description": "Search the public web for real-time information and return top citations.",
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "num_results": {"type": "integer", "description": "Number of results (1-10)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "web_fetch",
        "description": "Fetch a web page URL and extract its text content.",
        "schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "URL to fetch"}},
            "required": ["url"],
        },
    },

    # --- Windows Desktop Automation ---
    {
        "name": "windows_list_windows",
        "description": "List all open desktop application windows with titles and process IDs.",
        "schema": {"type": "object", "properties": {}},
    },
    {
        "name": "windows_list_processes",
        "description": "List running processes sorted by memory usage.",
        "schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Number of top processes to return (default 15)"}},
        },
    },
    {
        "name": "windows_take_screenshot",
        "description": "Take a screenshot of the Windows desktop and save it locally.",
        "schema": {
            "type": "object",
            "properties": {"filename": {"type": "string", "description": "Filename, e.g. 'desktop.png'"}},
        },
    },
    {
        "name": "windows_clipboard_get",
        "description": "Read text currently in the Windows clipboard.",
        "schema": {"type": "object", "properties": {}},
    },
    {
        "name": "windows_clipboard_set",
        "description": "Copy text to the Windows clipboard.",
        "schema": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Text to place on clipboard"}},
            "required": ["text"],
        },
    },
    {
        "name": "windows_open_app",
        "description": "Launch a Windows application (e.g. notepad, calc, explorer, cmd).",
        "schema": {
            "type": "object",
            "properties": {"app_name": {"type": "string", "description": "Application name to open"}},
            "required": ["app_name"],
        },
    },

    # --- Skills & Memory Tools ---
    {
        "name": "list_agent_skills",
        "description": "Search the bundled library of 58 Hermes skills by name or keyword.",
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional keyword or category"},
                "limit": {"type": "integer", "description": "Maximum results (default 80)"},
            },
        },
    },
    {
        "name": "read_skill",
        "description": "Read the full instructions and workflow specification of any bundled Hermes skill from skills/.",
        "schema": {
            "type": "object",
            "properties": {"skill_name": {"type": "string", "description": "Skill name or folder name"}},
            "required": ["skill_name"],
        },
    },
    {
        "name": "file_search",
        "description": "Search the persistent SQLite FTS5 index of user-indexed files and documents.",
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords or exact phrases"},
                "limit": {"type": "integer", "description": "Number of results (1-10)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "file_index_folder",
        "description": "Index a folder so all its documents remain searchable in persistent memory.",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or workspace folder path"},
                "recursive": {"type": "boolean", "description": "Include subfolders"},
                "force": {"type": "boolean", "description": "Re-index unchanged files"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "zip_archive_inventory",
        "description": "Inspect a ZIP archive's files, manifests, and README previews without extracting it.",
        "schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path to .zip archive"}},
            "required": ["path"],
        },
    },
    {
        "name": "local_runtime_info",
        "description": "Get runtime info (OS, workspace path, available tools, memory index size).",
        "schema": {"type": "object", "properties": {}},
    },
]


def local_runtime_info() -> dict[str, Any]:
    from .config import WORKSPACE_DIR, public_settings
    return {
        "os": platform.platform(),
        "workspace": str(WORKSPACE_DIR),
        "file_memory": file_memory.stats(),
        "configured_gemini_keys": public_settings()["gemini_key_count"],
        "active_model": public_settings()["gemini_model"],
        "mcp": {
            "configured_servers": mcp_bridge.status()["configured_servers"],
            "tool_count": mcp_bridge.status()["tool_count"],
        },
        "available_local_tools": len(LOCAL_TOOLS),
    }


def list_skills(query: str = "", limit: int = 100) -> list[dict[str, str]]:
    skills_dir = ROOT / "skills"
    found: list[dict[str, str]] = []
    normalized_query = query.casefold().strip()
    for file in sorted(skills_dir.rglob("SKILL.md")):
        content = file.read_text(encoding="utf-8", errors="replace")
        title = file.parent.name.replace("-", " ").title()
        for line in content.splitlines()[:14]:
            if line.startswith("name:"):
                title = line.split(":", 1)[1].strip() or title
                break
        description = ""
        for line in content.splitlines()[:30]:
            if line.startswith("description:"):
                description = line.split(":", 1)[1].strip().strip("'\"")
                break
        if not description:
            description = next(
                (line.strip(" #") for line in content.splitlines() if line.strip() and not line.strip().startswith(("---", "name:", "description:"))),
                "Workflow instructions",
            )
        path = str(file.relative_to(ROOT))
        if normalized_query and normalized_query not in f"{title} {description} {path}".casefold():
            continue
        found.append({"name": title, "path": path, "description": description[:240]})
    try:
        limit = max(1, min(250, int(limit)))
    except (TypeError, ValueError):
        limit = 100
    return found[:limit]


def execute_local_tool(name: str, arguments: dict[str, Any]) -> Any:
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be a JSON object.")

    # File & Folder Tools
    if name == "create_folder":
        return create_folder(str(arguments.get("path", "")))
    if name == "create_file":
        return create_file(str(arguments.get("path", "")), str(arguments.get("content", "")))
    if name == "read_file":
        start_line = int(arguments.get("start_line", 1) or 1)
        end_line = int(arguments["end_line"]) if arguments.get("end_line") is not None else None
        return read_file(str(arguments.get("path", "")), start_line, end_line)
    if name == "write_file":
        return write_file(str(arguments.get("path", "")), str(arguments.get("content", "")), bool(arguments.get("overwrite", True)))
    if name == "edit_file":
        return edit_file(str(arguments.get("path", "")), str(arguments.get("old_text", "")), str(arguments.get("new_text", "")))
    if name == "move_item":
        return move_item(str(arguments.get("source", "")), str(arguments.get("destination", "")))
    if name == "copy_item":
        return copy_item(str(arguments.get("source", "")), str(arguments.get("destination", "")))
    if name == "rename_item":
        return rename_item(str(arguments.get("path", "")), str(arguments.get("new_name", "")))
    if name == "delete_item":
        return delete_item(str(arguments.get("path", "")))
    if name == "compress_item":
        return compress_item(str(arguments.get("path", "")), str(arguments.get("format", "zip")), arguments.get("destination"))
    if name == "list_directory":
        return list_directory(str(arguments.get("path", "")), str(arguments.get("sort_by", "name")), bool(arguments.get("reverse", False)))
    if name == "analyze_document":
        return analyze_document(str(arguments.get("path", "")))

    # YouTube Downloader
    if name == "youtube_analyze":
        return youtube_analyze(str(arguments.get("url", "")))
    if name == "youtube_download":
        return youtube_download(
            str(arguments.get("url", "")),
            str(arguments.get("quality", "best")),
            str(arguments.get("output_format", "mp4")),
            str(arguments.get("engine", "auto")),
        )

    # Shell & Web
    if name == "run_command":
        return run_command(str(arguments.get("command", "")), int(arguments.get("timeout_seconds", 60)))
    if name == "web_search":
        return web_search(str(arguments.get("query", "")), int(arguments.get("num_results", 5)))
    if name == "web_fetch":
        return web_fetch(str(arguments.get("url", "")))

    # Windows Automation
    if name == "windows_list_windows":
        return windows_list_windows()
    if name == "windows_list_processes":
        return windows_list_processes(int(arguments.get("limit", 15)))
    if name == "windows_take_screenshot":
        return windows_take_screenshot(str(arguments.get("filename", "screenshot.png")))
    if name == "windows_clipboard_get":
        return windows_clipboard_get()
    if name == "windows_clipboard_set":
        return windows_clipboard_set(str(arguments.get("text", "")))
    if name == "windows_open_app":
        return windows_open_app(str(arguments.get("app_name", "")))

    # Skills & Memory
    if name == "list_agent_skills":
        return list_skills(str(arguments.get("query", "")), int(arguments.get("limit", 80)))
    if name == "read_skill":
        return read_skill(str(arguments.get("skill_name", "")))
    if name == "file_search":
        return file_memory.search(str(arguments.get("query", "")), int(arguments.get("limit", 8)))
    if name == "file_index_folder":
        return file_memory.index_folder(str(arguments.get("path", "")), bool(arguments.get("recursive", True)), bool(arguments.get("force", False)))
    if name == "zip_archive_inventory":
        return file_memory.analyze_archive(str(arguments.get("path", "")))
    if name == "local_runtime_info":
        return local_runtime_info()

    raise ValueError(f"Unknown local tool: {name}")


class ToolRegistry:
    def definitions(self, include_mcp: bool = True) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for tool in LOCAL_TOOLS:
            result.append({
                "name": tool["name"],
                "description": tool["description"],
                "schema": tool.get("schema", {}),
                "requires_approval": False,
                "server": "local",
            })
        if include_mcp:
            for tool in mcp_bridge.list_tools():
                result.append({
                    "name": tool["display_name"],
                    "description": tool.get("description", "Remote MCP tool"),
                    "schema": tool.get("input_schema", {}),
                    "requires_approval": True,
                    "server": tool["server_name"],
                    "original_name": tool["tool_name"],
                })
        return result

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        local_names = {tool["name"] for tool in LOCAL_TOOLS}
        if name in local_names:
            try:
                output = execute_local_tool(name, arguments)
                return {"ok": True, "tool": name, "result": output, "requires_approval": False}
            except Exception as exc:
                return {"ok": False, "tool": name, "error": f"{type(exc).__name__}: {str(exc)}"}

        # Remote MCP
        for tool in mcp_bridge.list_tools():
            if tool["display_name"] == name:
                approval_id = store.add_approval(tool["server_name"], tool["tool_name"], name, arguments)
                return {
                    "ok": True,
                    "approval_required": True,
                    "approval_id": approval_id,
                    "tool": name,
                    "message": "Windows MCP action queued for approval in the dashboard.",
                }
        return {"ok": False, "tool": name, "error": f"Unknown tool: {name}"}


registry = ToolRegistry()
