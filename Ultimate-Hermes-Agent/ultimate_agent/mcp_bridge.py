from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

from .config import load_settings


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not cleaned or not cleaned[0].isalpha():
        cleaned = "mcp_" + cleaned
    return cleaned[:96]


def _client_for(server: dict[str, Any]):
    try:
        from mcp import Client, StdioServerParameters
    except ImportError as exc:
        raise RuntimeError("MCP support is not installed. Run pip install -r requirements.txt.") from exc
    transport = str(server.get("transport", "stdio")).lower()
    if transport in {"http", "streamable-http", "url"}:
        url = str(server.get("url", "")).strip()
        if not url:
            raise ValueError(f"MCP server {server.get('name', 'unnamed')} has no URL.")
        return Client(url)
    command = str(server.get("command", "")).strip()
    if not command:
        raise ValueError(f"MCP server {server.get('name', 'unnamed')} has no command.")
    args = server.get("args", [])
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise ValueError("MCP server args must be a JSON array of strings.")
    env = server.get("env", {})
    if not isinstance(env, dict):
        raise ValueError("MCP server env must be a JSON object.")
    return Client(StdioServerParameters(command=command, args=args, env=({str(k): str(v) for k, v in env.items()} or None)))


class MCPBridge:
    def __init__(self) -> None:
        self._cache: list[dict[str, Any]] = []
        self._cache_at = 0.0
        self._error: str | None = None

    def _enabled_servers(self) -> list[dict[str, Any]]:
        settings = load_settings()
        return [server for server in settings.get("mcp_servers", [])
                if isinstance(server, dict) and server.get("enabled", False)]

    @staticmethod
    def _run(coro):
        # FastAPI's synchronous endpoints run in worker threads. A fresh loop per
        # operation keeps MCP sessions short-lived and avoids cross-loop reuse.
        return asyncio.run(coro)

    async def _list_tools_async(self) -> list[dict[str, Any]]:
        collected = []
        errors = []
        for index, server in enumerate(self._enabled_servers()):
            name = str(server.get("name") or f"server-{index + 1}")
            try:
                client_factory = _client_for(server)
                async with client_factory as client:
                    result = await client.list_tools()
                    for tool in result.tools:
                        original = str(tool.name)
                        collected.append({
                            "name": f"mcp_{_safe_name(name)[:24]}_{_safe_name(original)[:32]}",
                            "server_name": name,
                            "original_name": original,
                            "description": str(getattr(tool, "description", "") or "")[:1200],
                            "input_schema": getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None) or {"type": "object", "properties": {}},
                            "requires_approval": True,
                        })
            except Exception as exc:
                errors.append(f"{name}: {type(exc).__name__}: {str(exc)[:180]}")
        self._error = "; ".join(errors) if errors else None
        return collected

    def list_tools(self, force: bool = False) -> list[dict[str, Any]]:
        if not force and time.time() - self._cache_at < 20:
            return list(self._cache)
        self._cache = self._run(self._list_tools_async())
        self._cache_at = time.time()
        return list(self._cache)

    def status(self) -> dict[str, Any]:
        servers = self._enabled_servers()
        tools = self.list_tools()
        return {"configured_servers": len(servers), "enabled_servers": [s.get("name", "unnamed") for s in servers],
                "tool_count": len(tools), "error": self._error,
                "tools": [{k: v for k, v in item.items() if k != "input_schema"} for item in tools]}

    async def _call_async(self, server: dict[str, Any], tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async with _client_for(server) as client:
            result = await client.call_tool(tool_name, arguments)
            blocks = []
            for item in (getattr(result, "content", None) or []):
                block_type = type(item).__name__
                text = getattr(item, "text", None)
                if text is not None:
                    blocks.append({"type": block_type, "text": str(text)[:10000]})
            structured = getattr(result, "structured_content", None)
            return {"is_error": bool(getattr(result, "is_error", False)), "content": blocks,
                    "structured_content": structured}

    def call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        match = next((s for s in self._enabled_servers() if str(s.get("name") or "") == server_name), None)
        if match is None:
            raise ValueError("The configured MCP server is no longer enabled.")
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a JSON object.")
        return self._run(self._call_async(match, tool_name, arguments))


mcp_bridge = MCPBridge()
