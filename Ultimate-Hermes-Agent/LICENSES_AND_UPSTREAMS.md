# Licenses and upstream attribution

The uploaded archives contain multiple independent projects. Their licenses do not become one shared license merely because they are placed behind one dashboard. Review the full license text for each upstream before redistributing or deploying it.

| Included or referenced component | Upstream | Included files / use | License handling |
|---|---|---|---|
| Hermes skill library | Hermes Agent repository (`hermes-agent-main` in uploaded ZIP); project URL: https://github.com/NousResearch/hermes-agent | `skills/hermes-upstream/` | Original repository license copied to `upstream/HERMES_LICENSE`. Individual skill workflows may have their own notices or runtime requirements; preserve their file content and attribution. |
| Windows MCP server/CLI source | `mcp-windows-main` in uploaded ZIP | `upstream/mcp-windows/` source, README, feature catalogue, dependency props and license | Original `LICENSE` is retained at `upstream/mcp-windows/LICENSE`. The server is built/installed separately on Windows. |
| yt-dlp | https://github.com/yt-dlp/yt-dlp | Dependency declared in `requirements.txt`; not vendored | Install via PyPI; obey the project's current license and YouTube/service rules. |
| Google Gen AI SDK | https://googleapis.github.io/python-genai/ | Dependency declared in `requirements.txt`; not vendored | Install via PyPI and use an authorized Gemini API key/model. |
| FastAPI, Uvicorn, MCP Python SDK, pypdf, python-docx, openpyxl, python-dotenv | respective upstream projects | Dependencies declared in `requirements.txt`; not vendored | Their licenses apply to their distributions. |
| Autonomous AI Agent for Windows, Agent Zero, YouTube frontends, Analysis of Files, Bluey port, LibreChat, Open WebUI, Myraa | original projects contained in the uploaded ZIPs | Analyzed for features/integration; their entire codebases are not copied into this package | Consult the specific upstream license before integrating or redistributing those projects. Myraa `.env` and Firebase config are excluded. |

This package's new integration code is provided without a warranty. Nothing here grants permission to download copyrighted videos or bypass access controls. API users are responsible for complying with service terms, applicable law, and organizational policy.
