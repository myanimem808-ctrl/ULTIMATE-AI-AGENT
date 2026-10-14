# Build and validation record

Validation run for this source package on 2026-10-13:

- `python -m unittest discover -s tests -v` — **9 tests passed**.
- `python -m compileall -q .` — passed.
- `node --check static/app.js` — passed.
- FastAPI smoke checks for `/api/health`, `/api/state`, `/api/settings`, `/api/settings/configuration`, `/api/files/stats`, and `/api/skills` — all returned HTTP 200.
- File-memory tests cover indexing/search and verify `.env` values are skipped.
- Gemini failover tests cover missing keys, fallback after HTTP 429, secret-safe errors, and all-key failure behavior.
- YouTube tests cover public-host allowlisting and reject lookalike hosts / non-web schemes.

The validation runtime did not have `google-genai` or the MCP Python SDK installed, so no live Gemini call or MCP stdio handshake was performed in this container. Both dependencies are declared in `requirements.txt` and are installed by `install.bat`. No real YouTube download or FFmpeg media conversion was performed. The C# Windows MCP project has not been compiled to an `.exe` here; build it on Windows with the .NET 10 SDK using `build_windows_mcp.bat`.
