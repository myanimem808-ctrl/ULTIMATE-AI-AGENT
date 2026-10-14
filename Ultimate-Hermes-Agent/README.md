# Ultimate Hermes Agent Hub

A Windows-first local dashboard that combines the practical capabilities selected from the two uploaded ZIPs: multi-key Gemini failover, a persistent local file-memory index, bounded ZIP/repository inventory, asynchronous YouTube download jobs, an MCP tool registry, explicit approval for external Windows actions, and a searchable copy of the bundled Hermes skill library.

**Important architecture note:** this is a unified application hub and MCP adapter, not a claim that five independent AI platforms were flattened into one executable. Hermes, Agent Zero, LibreChat, Open WebUI, the desktop vision agent, and the two downloader frontends have distinct runtimes, providers, licenses, and dependency graphs. The app integrates the shared tools directly, includes Hermes skills and the Windows MCP source, and documents where the remaining upstream applications fit. The Windows MCP server and other local tools can be added without changing the Gemini agent core.

## Quick start (Windows 10/11)

1. Install **Python 3.11 or newer** (64-bit) and ensure `py` or `python` works in Command Prompt.
2. Extract this folder to a normal writable path, for example `C:\Tools\Ultimate-Hermes-Agent`.
3. Double-click `install.bat`. It creates `.venv`, installs dependencies, and copies `.env.example` to `.env` if needed.
4. Double-click `start.bat`. It opens the local dashboard at `http://127.0.0.1:8765`.
5. Open **Settings**, choose a Gemini model that your key can access, and enter one or more Gemini API keys separated by commas or newlines. Click **Save settings**.
6. Open **Assistant** and try: `Tell me what tools are available.`

The server deliberately binds only to the local loopback interface. Do not expose this unauthenticated dashboard to a LAN or the public internet.

## Gemini multi-key fallback

You can configure a list in **Settings**, or in `.env`:

```dotenv
GEMINI_API_KEYS=AIza...key_one,AIza...key_two,AIza...key_three
GEMINI_API_KEY=AIza...optional_single_key
GOOGLE_API_KEY=AIza...optional_google_key
GEMINI_MODEL=gemini-3.8-flash
APP_HOST=127.0.0.1
APP_PORT=8765
```

Keys are tried in rotating order. When a request fails with an authentication/permission error, rate limit, quota error, timeout, or selected transient server error, the key pool tries the next key once for that generation request. On a success, the next rotation starts after the successful key. Duplicate keys are removed. Key strings are never displayed by the dashboard health/status endpoints. Review Google's current API-key guidance at https://ai.google.dev/gemini-api/docs/generate-content/api-key and the official SDK documentation at https://googleapis.github.io/python-genai/.

**Fallback is resilience, not a quota bypass.** Keys from the same Google Cloud project may share quota, and invalid/restricted keys still fail. Use valid API keys and follow current Google AI Studio key policy. Keys entered in Settings are saved locally in `data/local_settings.json`; keep the folder private and do not commit or share that file. `.env` is ignored by Git. Google's guidance as of October 2026 says new AI Studio keys are authorization keys by default and unrestricted standard keys are rejected; review https://ai.google.dev/gemini-api/docs/generate-content/api-key before troubleshooting older keys.

## Included capabilities

- **Assistant:** Gemini function/tool-calling loop with request and tool-call bounds. Tool results, not assumptions, determine what the assistant reports.
- **Tool registry:** local functions plus tools discovered from configured MCP servers. New MCP servers can be added in Settings without editing the Python tool code.
- **Windows control:** configured MCP actions are shown as pending approvals and do not run until the user approves them in the dashboard. This includes clicks, typing, shell-side UI actions, clipboard changes, window/process control, and keyboard/mouse/screenshot tools exposed by the connected Windows MCP server.
- **File memory:** persistent SQLite/FTS search across explicitly selected folders. Supports common source/text formats, PDF text layers, DOCX paragraphs/tables, and XLSX values. It reads files and does not edit their source content. Indexing is bounded, skips vendor/cache/build directories, and skips common credential files such as `.env` and private-key containers.
- **ZIP inventory:** lists top-level repositories, file extensions, selected tool/skill/manifest paths, and README previews without extracting or executing archive content.
- **YouTube tools:** analyze public YouTube/youtu.be links, inspect formats, select resolution, and queue background MP4/MKV or MP3/M4A jobs with progress information. Requires FFmpeg for stream merging/audio conversion and follows the service's rights/terms restrictions.
- **Skills Library:** includes the 58 `SKILL.md` workflows and supporting files found under Hermes' `skills/` directory in the uploaded archive, subject to upstream licensing. Skill prompts are knowledge/instructions; a skill that requires a missing connector or platform does not magically gain that dependency.
- **MCP server mode:** `mcp_server.py` exposes file memory, ZIP inventory, YouTube analysis/download, and skill lookup over MCP stdio. Use it from Hermes or another MCP host.
- **Emergency stop:** blocks new assistant tool execution and pending Windows MCP approvals. It does not undo actions that have already completed.

## Add Windows UI automation tools

The source for the uploaded Windows MCP server is included in `upstream/mcp-windows/` with its upstream `LICENSE`, README, and feature catalogue. It targets **.NET 10 / Windows 10.0.22621+**.

1. Install the .NET 10 SDK on Windows.
2. From this folder, build/publish the MCP server (PowerShell):

   ```powershell
   dotnet publish .\upstream\mcp-windows\src\Sbroenne.WindowsMcp\Sbroenne.WindowsMcp.csproj -c Release -o .\upstream\mcp-windows\publish
   ```

3. In the dashboard go to **Settings → MCP servers**, then add a JSON array entry (replace the absolute path with your real folder path):

   ```json
   [
     {
       "name": "windows",
       "enabled": true,
       "transport": "stdio",
       "command": "C:\\Tools\\Ultimate-Hermes-Agent\\upstream\\mcp-windows\\publish\\Sbroenne.WindowsMcp.exe",
       "args": [],
       "env": {}
     }
   ]
   ```

4. Save settings, open **Windows Tools**, and use **Refresh tools**. The dashboard will discover the server's exposed tools. Every action invoked through the assistant is queued for explicit approval.

If the published `.exe` is missing due to the project being framework-dependent, run it with the .NET host instead: `command: "dotnet"`, `args: ["C:\\...\\Sbroenne.WindowsMcp.dll"]`.

The uploaded Windows MCP repo includes accessibility/UI Automation and command-line tooling. Review `upstream/mcp-windows/FEATURES.md` and `upstream/mcp-windows/README.md` for tool preconditions, elevation limitations, and detailed examples.

## Connect this program to Hermes Agent

The bundled `mcp_server.py` is a stdio MCP server. After `install.bat`, configure it in Hermes' `~/.hermes/config.yaml` (on Windows, use the path to the Python executable and script that exist on your machine):

```yaml
mcp_servers:
  ultimate-local-tools:
    command: "C:/Tools/Ultimate-Hermes-Agent/.venv/Scripts/python.exe"
    args:
      - "C:/Tools/Ultimate-Hermes-Agent/mcp_server.py"
```

Restart Hermes and check that the server's tools are discovered. Official Hermes MCP configuration docs: https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp

This arrangement is intentional: Hermes keeps its native CLI/session history, memory/learning, scheduled jobs, subagents, provider support, terminal backends, and messaging gateway; the hub supplies the bundled local tools and custom dashboard. A separate Gemini-key-pool agent is available directly in the dashboard for a Windows-first user experience.

## YouTube download prerequisites and limits

- Install FFmpeg and add `ffmpeg.exe` to your `PATH` for combining separate video/audio streams and converting audio.
- Download only content you own, are licensed to download, or are otherwise legally permitted to save. The user is responsible for checking applicable law and service terms.
- Only YouTube and youtu.be URL hosts are accepted by the downloader.
- yt-dlp changes frequently; if a download stops working, update it with `.venv\Scripts\python.exe -m pip install --upgrade yt-dlp`.

## Dashboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+K` | Focus the assistant input |
| `Ctrl+Enter` | Send the current assistant prompt |
| `Ctrl+Shift+Q` | Trigger this app's emergency stop while the dashboard tab has focus |
| `Esc` | Clear the current message input |

The full Windows shortcut reference supplied in the second ZIP is preserved at `docs/windows_keyboard_shortcuts_reference.txt`. Hermes CLI keybindings and slash commands are summarized in `SHORTCUTS.md`; the bundled upstream references are `docs/hermes_cli_reference.md` and `docs/hermes_slash_commands_reference.md`. Check the current official CLI guide at https://hermes-agent.nousresearch.com/docs/user-guide/cli because shortcuts may vary by installed version and terminal.

## API routes

The local API docs are at `http://127.0.0.1:8765/api/docs` while the app is running. Important routes include `/api/chat`, `/api/tools`, `/api/files/index`, `/api/files/search`, `/api/archives/analyze`, `/api/youtube/analyze`, `/api/youtube/download`, `/api/mcp/status`, `/api/approvals`, and `/api/emergency-stop`.

## Data and privacy

- `data/local_settings.json`: local settings and keys entered through Settings.
- `data/app.sqlite3`: chat history and approval queue.
- `data/file_memory.sqlite3`: extracted text chunks and file metadata for files you explicitly indexed.
- `data/downloads/`: downloads made through the app.
- `workspace/`: intended local workspace area.
- No populated `.env`, Firebase config, API credential file, SQLite data, or downloaded video is included in this package. The credential-bearing Myraa files found in the uploaded ZIP were excluded.

## Tests and troubleshooting

Run local tests after installation:

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m compileall -q .
```

- **No keys configured:** enter at least one key in Settings or `.env`.
- **Model not available:** set the model to one enabled for your key/account.
- **All keys failed:** check key restrictions, model access, network connectivity, and quota. Fallback cannot bypass shared project quota.
- **No downloads:** install FFmpeg and update yt-dlp.
- **No Windows tools:** install/publish the .NET MCP server, add it in MCP settings, and refresh.
- **MCP server error:** check the configured command/path, JSON syntax, server runtime dependencies, and Windows UI privilege/elevation boundaries.

## License and upstreams

See `LICENSES_AND_UPSTREAMS.md` and the per-upstream license files. This project contains integration code plus selected upstream skill/source files. Respect original licenses and the terms of any service/API you connect.
