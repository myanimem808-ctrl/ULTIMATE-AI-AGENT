# Uploaded ZIP analysis and integration map

This report summarizes the two uploaded archives, separates executable project source from bundled dependencies/build output, and maps what is wired into this hub versus what remains an optional upstream application.

## Scope and package hygiene

| Upload | ZIP entries | Approx. uncompressed size | Main projects identified |
|---|---:|---:|---|
| `Autonomous-AI-Agent-For-Windows-main (1).zip` | 16,672 | 373.9 MB | Autonomous AI Agent for Windows, Agent Zero, two YouTube downloader projects, file analysis tool, Bluey Windows/Android port, parity-workbench assets |
| `mcp-windows-main.zip` | 32,998 | 357.6 MB | Hermes Agent, Windows MCP, LibreChat, Open WebUI, Myraa AI companion, Windows shortcut reference, sandbox/skills inventory, small Windows utilities/sound assets |

The archives contain large amounts of `.venv`, `.next`, `.git`, dependency, test-fixture, and generated material. These are not copied into the runnable hub. The package preserves the 58 Hermes `SKILL.md` workflows plus supporting skill files (440 files), and the relevant source/docs/licenses for the 5.3 MB Windows MCP repository subset (~1.5 MB copied source). The two original YouTube implementations are not duplicated as separate frontends; their main useful download pipeline is implemented in one background job service using yt-dlp and FFmpeg.

## Repository-by-repository map

| Source project | Core features found in archive | What this package does with it | What remains external / not merged |
|---|---|---|---|
| **Hermes Agent** (`hermes-agent-main`) | CLI/TUI, provider support, messages/gateway, persistent memory and learning, session search, skills, scheduled tasks/cron, parallel subagents, multiple terminal backends, MCP tools, interrupt/redirect and slash commands | Copies upstream skills with supporting files; supplies `mcp_server.py` so Hermes can call this hub's file-memory/ZIP/YouTube tools. The official Hermes MCP config snippet is in README. | Hermes' own CLI/gateway/scheduler/subagent runtime remains the upstream Hermes install. The dashboard is not a full reimplementation of that runtime. |
| **Windows MCP** (`mcp-windows-main`) | Windows accessibility tree, UI find/click/type/read/table/select/wait/batch/snapshot, keyboard/mouse, clipboard, process/window controls, screenshots, CLI `wincli` | Includes Windows MCP source, project dependencies files, features/docs, and license under `upstream/mcp-windows/`. Hub's MCP bridge discovers tools dynamically; every remote tool action is approval-gated. | It still must be published on the target Windows machine with .NET 10. Tool availability depends on OS privileges and Windows accessibility support. |
| **Autonomous AI Agent for Windows** | Vision + DOM hybrid flow, OmniParser screen perception, Playwright browser DOM, planner/navigator/verifier roles, provider per role, skills and human-in-the-loop controls, `Ctrl+Shift+Q` emergency stop | Tool-registry/approval pattern and emergency-stop concept are adapted; Windows MCP supplies desktop/UI automation through a more reusable protocol. | OmniParser model downloads, dedicated planner/navigator/verifier agents, and its original FastAPI/Playwright backend are not copied as a complete separate runtime. |
| **4K YouTube downloader UI** (`4k yt v2`) | React/Next-style download workspace, video metadata and quality selection UI | Consolidated into the dashboard's YouTube panel and API. | Original separate frontend is not bundled. |
| **YouTube 4K downloader backend** (`4k yt video downalod`) | FastAPI + yt-dlp + FFmpeg, resolution discovery to 2160p, MP4/MKV and MP3/M4A, async jobs, progress/speed/ETA | Rebuilt as `ultimate_agent/youtube.py` and `/api/youtube/*` endpoints; adds host validation, output filename guarding, bounded formats, error/progress fields. | Uses upstream yt-dlp; YouTube behavior/service terms can change. FFmpeg is an external executable prerequisite. |
| **Analysis of Files** (`analsysis_of_files`) | Directory/file scanner, persistent SQLite store, document text extraction and model-assisted summaries, interactive shell | Upgraded conceptually to persistent SQLite + FTS5 chunk index (`ultimate_agent/file_memory.py`), PDF/DOCX/XLSX extraction, folder indexing, search/stat endpoints, and archive inventory. | LM Studio summarization and its original interactive shell are not copied. The current implementation stores searchable source excerpts; it does not automatically generate abstractive summaries. |
| **Agent Zero** (`agent-zero-main`) | Multi-agent framework, separate Dockerized desktop/browser, project memory, host CLI bridge, plugins, prompt/tool customization and coworking | Mapped as an optional upstream agent in this architecture; Hermes' MCP interoperability is preferred as the shared tool boundary. | Entire Agent Zero framework, Docker runtime and its web desktop are not flattened into the hub. |
| **Bluey Windows/Android port** | Windows overlay/UI automation, phone/companion service, screen reading, meeting notes, credential store, platform ports | Analyzed for capability overlap; the shared local tool/MCP approach avoids duplicating overlapping desktop controls. | Cross-device ports, phone server, note-taking/meeting services, and its original app shell are not copied. Potentially risky system-modification scripts (e.g., firewall mutation) are intentionally not bundled. |
| **LibreChat** | Provider-rich chat frontend, agents/MCP, RAG/vector databases, browsing/search, voice/video, image features, integrations, analytics/auth/cloud storage | Mapped as an optional full chat platform, not as a Python module. Hub has a lightweight local dashboard and MCP support instead. | LibreChat's independent Node/Postgres/storage/auth and model-provider stack is not included or rewritten. |
| **Open WebUI** | Local/cloud model UI, RAG/documents/vector database, web search, voice/image generation, artifacts, authentication/analytics | Mapped as an optional full platform. File-memory core and chat tools are separately exposed by this hub. | Open WebUI's Svelte/Python backend, auth stack, model connectors and full UI are not embedded. |
| **Myraa AI assistant** | Gemini/Google GenAI React/Vite/Electron assistant and companion/memory features | Used only as architectural reference. | A populated `.env` and Firebase applet config were present. Those files and their values are explicitly excluded; rotate any real keys that were previously shared with untrusted parties. |
| **Windows shortcut reference** | Broad Windows keybindings and accessibility/navigation shortcuts | The uploaded `windows_keyboard_shortcuts.txt` is preserved as `docs/windows_keyboard_shortcuts_reference.txt`; dashboard keys are in README/SHORTCUTS.md. | Windows shortcuts depend on Windows version and active application. |
| **Small utility scripts** (`installed_apps_tooll.py`, `wifi_speed_test.py`) | Installed app inventory and Wi-Fi speed checking | Inventory captured. | Not automatically executed: these are machine-specific external checks, not safe side effects to run during package startup. |
| **Parity Workbench / alert assets** | Node parity workbench, parity/dependency helper, alarm/audio resources | Source inventory noted. | Not part of the core application; launch and dependencies aren't wired into the dashboard. |

## Unified data flow

```text
Dashboard (local browser)
  ├─ Assistant ── Gemini key pool (round-robin + request-level failover)
  │     ├─ Local tool registry
  │     │    ├─ File memory (SQLite / FTS5)
  │     │    ├─ Safe ZIP inventory
  │     │    ├─ YouTube analyze/download job queue (yt-dlp + FFmpeg)
  │     │    └─ Hermes skill metadata search
  │     └─ Remote MCP registry ── explicit approval queue ── Windows MCP / other MCP servers
  ├─ File Memory (index/search/stats)
  ├─ YouTube job monitor (queue/progress/download files)
  ├─ MCP server status and approval controls
  └─ Settings (Gemini model, multiple keys, MCP command/args/env)

Hermes Agent or another MCP host
  └─ stdio process: mcp_server.py
       ├─ file_search / file_index_folder
       ├─ zip_archive_inventory
       ├─ youtube_analyze / youtube_download
       └─ list_agent_skills_json
```

## Key implementation decisions

1. **MCP is the integration boundary.** Each upstream project has different runtime assumptions. Adding/removing an MCP server lets tool-capable clients discover tools without tightly coupling repositories.
2. **No default computer action executes silently.** Remote MCP tools enter an approval queue. The user must explicitly approve each remote call in the dashboard; a pending action is denied/blocked while emergency stop is active.
3. **File memory is local and persistent.** SQLite stores indexed text chunks and metadata; FTS5 retrieves matching excerpts. A file must be indexed before it becomes searchable. The index can contain sensitive excerpts, so choose folders deliberately and protect `data/`. Common credential files (`.env`, PEM/PFX/key files, selected credential JSON files) are skipped by the indexer.
4. **ZIP files are inspected, not extracted or run.** Archive inventory is bounded by entry count and total uncompressed bytes, and is read-only.
5. **Fallback does not bypass Google quota.** The pool rotates across configured keys only after classified errors. Keys from one Cloud project can share quota; multi-key setup improves resilience only when keys have valid independent access/quota where applicable. Google’s current policy distinguishes standard and authorization keys; new AI Studio keys are auth keys by default and unrestricted standard keys are rejected (see https://ai.google.dev/gemini-api/docs/generate-content/api-key).
6. **One service surface; multiple upstream engines remain possible.** The local dashboard supplies essential combined tasks; the full Hermes agent remains responsible for its own session, scheduler, gateway and subagent features when launched from its native installation.

## Known implementation boundaries

- This package is source-code complete for the included dashboard/tool server, but no Windows `.exe` has been compiled here; publish the included C# Windows MCP project on the target device.
- No network Gemini request or real YouTube download was executed during local verification; those require the user's API key/network/media URL and FFmpeg.
- Hermes skill files may refer to provider credentials, connectors, macOS, or other software that is not installed here. The library makes the workflows searchable, but does not automatically fulfill missing external dependencies.
- Full Agent Zero, LibreChat, Open WebUI and the separate desktop vision agent remain independent upstream projects. Calling this literal byte-for-byte union would be inaccurate; this is the consolidated hub and integration layer.
