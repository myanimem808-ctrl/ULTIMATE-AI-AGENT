# Keyboard shortcuts

## Ultimate Hermes Agent Hub dashboard

These shortcuts apply only while the dashboard browser tab is focused.

| Keys | Effect |
|---|---|
| `Ctrl+K` | Focus the assistant prompt field from any dashboard page |
| `Ctrl+Enter` | Send the current assistant prompt |
| `Ctrl+Shift+Q` | Activate the dashboard's emergency stop; prevents new tool actions/pending approvals, but cannot undo completed work |
| `Esc` | Clear the active input/textarea |

## Hermes Agent terminal CLI (TUI)

The uploaded Hermes CLI guide contains the detailed keybindings and terminal-specific exceptions at `docs/hermes_cli_reference.md`. Common bindings in that guide are:

| Keys | Effect |
|---|---|
| `Enter` | Send message |
| `Ctrl+J` or `Alt+Enter` | Insert a newline in a multiline prompt |
| `Shift+Enter` | Insert a newline only when the terminal sends a distinct key sequence |
| `Ctrl+V` | Paste text; may also attach clipboard images when supported |
| `Alt+V` | Paste an image from the clipboard when supported |
| `Ctrl+B` | Start/stop voice recording when voice mode is enabled |
| `Ctrl+G` | Open the current prompt in `$EDITOR` |
| `Ctrl+X`, then `Ctrl+E` | Alternate external-editor shortcut |
| `Ctrl+S` | Stash a draft; press again on an empty prompt to restore/browse stashed drafts |
| `Ctrl+C` | Clear a typed draft first; if prompt is empty, interrupt the current operation. Double-press within two seconds forces exit |
| `Ctrl+T` / `F6` | Open the live work monitor |
| `Ctrl+R` / `F7` | Toggle the live-work dock layout |
| `Ctrl+D` | Exit the CLI |
| `Tab` | Accept an auto-suggestion or autocomplete slash commands |
| `!command` | Run a shell command in Hermes CLI shell mode instead of sending it to the model |

**Windows Terminal note from the bundled Hermes guide:** `Alt+Enter` is usually captured by Windows Terminal as a fullscreen toggle; use `Ctrl+J` or `Ctrl+Enter` for a newline in Hermes CLI. Stock Windows Terminal may not distinguish `Shift+Enter` unless its keyboard protocol support is enabled. These keys differ from the dashboard's own `Ctrl+Enter` action.

Slash-command reference: `docs/hermes_slash_commands_reference.md`. Slash command availability can change with Hermes version and installed skills.

## Windows OS shortcuts

The full broad Windows shortcut reference supplied in the second ZIP is preserved in `docs/windows_keyboard_shortcuts_reference.txt`. Windows shortcuts depend on Windows version, keyboard layout, and active application.
