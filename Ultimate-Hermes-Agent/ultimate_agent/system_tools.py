from __future__ import annotations

import os
import re
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any

from .config import DATA_DIR, ROOT, WORKSPACE_DIR

try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None


def run_command(command: str, timeout_seconds: int = 60) -> dict[str, Any]:
    """Execute a shell command inside the workspace directory."""
    cmd = (command or "").strip()
    if not cmd:
        raise ValueError("Command cannot be empty.")

    # Guard against accidental catastrophic recursive system deletion commands
    lowered = cmd.lower()
    if any(danger in lowered for danger in ["format c:", "del /s /q c:\\", "rmdir /s /q c:\\"]):
        raise PermissionError("Dangerous system command blocked.")

    timeout = max(1, min(300, int(timeout_seconds)))
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=str(WORKSPACE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            errors="replace",
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-12000:],
            "stderr": proc.stderr[-6000:],
            "command": cmd,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Command timed out after {timeout} seconds.", "command": cmd}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)}", "command": cmd}


def web_fetch(url: str) -> dict[str, Any]:
    """Fetch content of a URL and strip HTML into clean text."""
    import requests
    target_url = (url or "").strip()
    if not target_url.startswith(("http://", "https://")):
        target_url = "https://" + target_url

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) UltimateHermes/1.0"}
    resp = requests.get(target_url, headers=headers, timeout=15)
    resp.raise_for_status()
    
    html = resp.text
    # Strip script/style
    clean = re.sub(r"<(script|style)[\s\S]*?</\1>", "", html, flags=re.IGNORECASE)
    # Strip tags
    text = re.sub(r"<[^>]+>", " ", clean)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    
    return {
        "ok": True,
        "url": target_url,
        "status_code": resp.status_code,
        "text_content": text[:16000],
    }


def web_search(query: str, num_results: int = 5) -> dict[str, Any]:
    """Search web using DuckDuckGo HTML / public search endpoint."""
    import requests
    q = (query or "").strip()
    if not q:
        raise ValueError("Search query cannot be empty.")

    limit = max(1, min(10, int(num_results)))
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(q)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) UltimateHermes/1.0"}
    resp = requests.get(url, headers=headers, timeout=12)
    resp.raise_for_status()

    results = []
    blocks = re.findall(r'<a class="result__url"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>[\s\S]*?<a class="result__snippet"[^>]*>([\s\S]*?)</a>', resp.text)
    for raw_url, raw_title, raw_snippet in blocks[:limit]:
        title = re.sub(r"<[^>]+>", "", raw_title).strip()
        snippet = re.sub(r"<[^>]+>", "", raw_snippet).strip()
        # Decode duckduckgo redirect url if present
        clean_url = raw_url
        if "uddg=" in raw_url:
            m = re.search(r"uddg=([^&]+)", raw_url)
            if m:
                clean_url = urllib.parse.unquote(m.group(1))
        results.append({"title": title or clean_url, "url": clean_url, "snippet": snippet})

    return {"ok": True, "query": q, "results": results}


def windows_list_windows() -> dict[str, Any]:
    """List open visible application windows on Windows."""
    script = """
    Get-Process | Where-Object { $_.MainWindowTitle } | Select-Object Id, ProcessName, MainWindowTitle | ConvertTo-Json
    """
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True)
    import json
    try:
        data = json.loads(proc.stdout)
        windows = data if isinstance(data, list) else [data]
        return {"ok": True, "windows": windows}
    except Exception:
        return {"ok": True, "raw": proc.stdout.strip()}


def windows_list_processes(limit: int = 15) -> dict[str, Any]:
    """List active processes by CPU / memory."""
    script = f"""
    Get-Process | Sort-Object -Property WorkingSet -Descending | Select-Object -First {limit} Id, ProcessName, WorkingSet64 | ConvertTo-Json
    """
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True)
    import json
    try:
        data = json.loads(proc.stdout)
        items = data if isinstance(data, list) else [data]
        formatted = []
        for p in items:
            ws = p.get("WorkingSet64", 0) or 0
            formatted.append({
                "pid": p.get("Id"),
                "name": p.get("ProcessName"),
                "memory_mb": round(ws / (1024 * 1024), 1),
            })
        return {"ok": True, "processes": formatted}
    except Exception:
        return {"ok": True, "raw": proc.stdout.strip()}


def windows_take_screenshot(filename: str = "screenshot.png") -> dict[str, Any]:
    """Capture a screenshot of the desktop screen."""
    clean_name = Path(filename).name
    if not clean_name.lower().endswith((".png", ".jpg", ".jpeg")):
        clean_name += ".png"
    out_path = DATA_DIR / clean_name
    
    if ImageGrab is not None:
        img = ImageGrab.grab()
        img.save(str(out_path))
        return {"ok": True, "path": str(out_path), "resolution": list(img.size), "file_name": clean_name}

    # Fallback using PowerShell
    ps_cmd = f"""
    Add-Type -AssemblyName System.Windows.Forms,System.Drawing
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
    $bmp.Save('{str(out_path)}')
    $g.Dispose()
    $bmp.Dispose()
    """
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True)
    return {"ok": True, "path": str(out_path), "file_name": clean_name}


def windows_clipboard_get() -> dict[str, Any]:
    """Get current clipboard text."""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"], capture_output=True, text=True)
    return {"ok": True, "clipboard_text": proc.stdout.strip()[:10000]}


def windows_clipboard_set(text: str) -> dict[str, Any]:
    """Set system clipboard text."""
    p = subprocess.Popen(["clip"], stdin=subprocess.PIPE, text=True)
    p.communicate(input=text)
    return {"ok": True, "message": f"Copied {len(text)} characters to clipboard."}


def windows_open_app(app_name: str) -> dict[str, Any]:
    """Open a common desktop application or file."""
    app = (app_name or "").strip()
    if not app:
        raise ValueError("App name cannot be empty.")
    
    # Safe lookup for common apps
    known_apps = {
        "notepad": "notepad.exe",
        "calc": "calc.exe",
        "calculator": "calc.exe",
        "explorer": "explorer.exe",
        "cmd": "cmd.exe",
        "powershell": "powershell.exe",
        "paint": "mspaint.exe",
    }
    target = known_apps.get(app.lower(), app)
    subprocess.Popen(f'start "" "{target}"', shell=True)
    return {"ok": True, "launched": target}


def read_skill(skill_path_or_name: str) -> dict[str, Any]:
    """Read full SKILL.md instructions for any of the 58 bundled Hermes skills."""
    query = (skill_path_or_name or "").strip().lower()
    skills_dir = ROOT / "skills"
    
    matched = None
    for file in skills_dir.rglob("SKILL.md"):
        rel = str(file.relative_to(ROOT)).lower().replace("\\", "/")
        parent_name = file.parent.name.lower()
        if query in rel or query in parent_name:
            matched = file
            break
            
    if not matched:
        raise FileNotFoundError(f"Skill '{skill_path_or_name}' not found under skills/ directory.")
        
    content = matched.read_text(encoding="utf-8", errors="replace")
    return {
        "ok": True,
        "skill_path": str(matched.relative_to(ROOT)),
        "instructions": content[:30000],
    }
