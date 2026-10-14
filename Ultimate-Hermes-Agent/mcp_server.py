"""Expose the hub's local tools to Hermes Agent and other MCP-compatible hosts.

Run this script as an MCP stdio subprocess. Do not launch it directly in a normal
terminal expecting a web UI; start start.bat for the dashboard.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from mcp.server import MCPServer

from ultimate_agent.file_memory import file_memory
from ultimate_agent.tools import list_skills
from ultimate_agent.youtube import analyze as youtube_analyze, start_download as youtube_download

mcp = MCPServer("ultimate-hermes-tools", instructions=(
    "Local-first tools for file-memory search, bounded ZIP inspection, and requested public YouTube downloads. "
    "Do not claim actions succeeded without checking results. Windows UI tools are configured separately through Windows MCP."
))


@mcp.tool()
def file_search(query: str, limit: int = 8) -> str:
    """Search indexed local file excerpts. Index a folder first using file_index_folder."""
    return json.dumps(file_memory.search(query, limit), ensure_ascii=False)


@mcp.tool()
def file_index_folder(path: str, recursive: bool = True, force: bool = False) -> str:
    """Index a user-selected local folder into a persistent searchable SQLite memory store. This reads files and does not change source files."""
    return json.dumps(file_memory.index_folder(path, recursive, force), ensure_ascii=False)


@mcp.tool()
def zip_archive_inventory(path: str) -> str:
    """Inspect a ZIP's top-level projects, README previews, manifest, tool, and skill paths without extracting or executing the archive."""
    return json.dumps(file_memory.analyze_archive(path), ensure_ascii=False)


@mcp.tool()
def youtube_analyze(url: str) -> str:
    """Inspect metadata and available resolutions for a public YouTube/youtu.be video."""
    return json.dumps(youtube_analyze(url), ensure_ascii=False)


@mcp.tool()
def youtube_download(url: str, quality: str = "best", output_format: str = "mp4") -> str:
    """Start a background YouTube download in MP4, MKV, MP3, or M4A. Use only at the user's request and respect rights and service terms. Returns job ID."""
    return json.dumps(youtube_download(url, quality, output_format), ensure_ascii=False)


@mcp.tool()
def list_agent_skills_json(query: str = "", limit: int = 80) -> str:
    """Search local workflow skill metadata by keyword/category."""
    return json.dumps(list_skills(query, limit), ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
