# Folder Export: working_tools

Source path: `C:\Users\My PC\Documents\Ultimate-Hermes-Agent\ALL_PROGRAMS\working_tools`

## File Structure

```
working_tools/
├── installed_apps_tooll.py
└── wifi_speed_test.py
```

## File Contents

### `installed_apps_tooll.py`

```python
"""
apps_tool.py
=================================================================
A lightweight, zero-background-usage tool to track installed and 
default Windows applications. 

It maintains a local JSON database to remember app states and 
can detect what has been installed or uninstalled since the last run.
=================================================================
"""

import winreg
import subprocess
import json
import os
import sys

# The local database file where the tool remembers your apps
DATABASE_FILE = "apps_database.json"

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def section(title):
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)

# ----------------------------------------------------------------------
# Core Scanning Functions (Ultra-Low CPU/RAM via Registry)
# ----------------------------------------------------------------------

def get_installed_apps():
    """
    Scans the Windows Registry for standard desktop programs (Win32).
    This is hundreds of times faster and uses less RAM than WMI or PowerShell.
    """
    apps = set()
    registry_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
    ]

    for hive, subkey in registry_paths:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        sub = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, sub) as app_key:
                            try:
                                name = winreg.QueryValueEx(app_key, "DisplayName")[0]
                                # Filter out raw Windows Updates so the list stays clean
                                if name and not name.startswith("KB") and "Update" not in sub:
                                    apps.add(name.strip())
                            except FileNotFoundError:
                                # App has no DisplayName, ignore it
                                continue
                    except OSError:
                        continue
        except OSError:
            continue
            
    return sorted(list(apps))


def get_default_apps():
    """
    Scans for Default/Modern Windows Apps (UWP/Store Apps).
    Uses a highly targeted PowerShell command to exclude hidden frameworks.
    """
    ps_cmd = (
        "Get-AppxPackage -User $env:USERNAME | "
        "Where-Object {$_.IsFramework -eq $false -and $_.NonRemovable -eq $false} | "
        "Select-Object -ExpandProperty Name"
    )
    
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0:
            # Clean up the output list
            raw_apps = result.stdout.strip().splitlines()
            clean_apps = [app.strip() for app in raw_apps if app.strip()]
            return sorted(clean_apps)
        return []
    except Exception:
        return []

# ----------------------------------------------------------------------
# Database & Memory Functions
# ----------------------------------------------------------------------

def load_database():
    """Loads the remembered apps from the local JSON file."""
    if not os.path.exists(DATABASE_FILE):
        return {"installed": [], "default": []}
    try:
        with open(DATABASE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"installed": [], "default": []}


def save_database(data):
    """Saves the current state of apps to the local JSON file."""
    try:
        with open(DATABASE_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving database: {e}")


def sync_and_detect_changes():
    """
    Scans the system, compares it to the database, detects installs/uninstalls, 
    and updates the database if necessary.
    """
    print("Scanning system... (This is optimized for low CPU/RAM)")
    
    current_installed = get_installed_apps()
    current_default = get_default_apps()
    
    db = load_database()
    old_installed = set(db.get("installed", []))
    old_default = set(db.get("default", []))
    
    cur_installed_set = set(current_installed)
    cur_default_set = set(current_default)
    
    # Calculate differences (What is new? What is gone?)
    new_installed = cur_installed_set - old_installed
    rem_installed = old_installed - cur_installed_set
    
    new_default = cur_default_set - old_default
    rem_default = old_default - cur_default_set
    
    changes_detected = False

    if new_installed or new_default or rem_installed or rem_default:
        changes_detected = True
        clear_screen()
        section("SYSTEM CHANGES DETECTED SINCE LAST RUN")
        
        for app in new_installed:
            print(f"  [+] INSTALLED: {app}")
        for app in new_default:
            print(f"  [+] INSTALLED (Default App): {app}")
            
        for app in rem_installed:
            print(f"  [-] UNINSTALLED: {app}")
        for app in rem_default:
            print(f"  [-] UNINSTALLED (Default App): {app}")
            
        print("\nUpdating local database to remember these changes...")
        
        # Update and save
        db["installed"] = current_installed
        db["default"] = current_default
        save_database(db)
        input("\nPress Enter to continue to the main menu...")
    else:
        # If it's the very first time running, save quietly
        if not old_installed and not old_default:
            db["installed"] = current_installed
            db["default"] = current_default
            save_database(db)

    return db

# ----------------------------------------------------------------------
# Main Menu
# ----------------------------------------------------------------------

def main():
    # Sync memory on startup
    clear_screen()
    db = sync_and_detect_changes()
    
    while True:
        clear_screen()
        print("=" * 60)
        print(" WINDOWS APP TRACKER  (apps_tool.py)")
        print(" Database state: UP TO DATE")
        print("=" * 60)
        print("  [1] Show Installed Apps")
        print("  [2] Show Default Apps")
        print("  [0] Exit")
        print("-" * 60)
        
        choice = input("Select an option: ").strip()
        
        if choice == "0":
            sys.exit(0)
            
        elif choice == "1":
            section("INSTALLED APPS")
            for app in db.get("installed", []):
                print(app)
            input("\nPress Enter to go back...")
            
        elif choice == "2":
            section("DEFAULT APPS")
            for app in db.get("default", []):
                print(app)
            input("\nPress Enter to go back...")
            
        else:
            continue

if __name__ == "__main__":
    if os.name != "nt":
        print("This tool is designed for Windows.")
        sys.exit(1)
    main()
```

### `wifi_speed_test.py`

```python
# pip install requests colorama

import os
import sys
import time
import random
import threading
import requests
from colorama import init, Fore, Style

init(autoreset=True)

PING_URL      = "https://speed.cloudflare.com/__down?bytes=1"
DOWNLOAD_URL  = "https://speed.cloudflare.com/__down?bytes=25000000"
UPLOAD_URL    = "https://speed.cloudflare.com/__up"
TIMEOUT       = 30
PING_ROUNDS   = 10


# ── Spinner ────────────────────────────────────────────────────────────────────

class Spinner:
    _frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str):
        self.message  = message
        self._stop    = threading.Event()
        self._thread  = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        idx = 0
        while not self._stop.is_set():
            frame = self._frames[idx % len(self._frames)]
            sys.stdout.write(f"\r {Fore.CYAN}{frame}{Style.RESET_ALL}  {self.message}   ")
            sys.stdout.flush()
            time.sleep(0.08)
            idx += 1

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join()
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.stdout.flush()


# ── Colour helpers ─────────────────────────────────────────────────────────────

def colour_ping(ms: float) -> str:
    val = f"{ms:>6.1f} ms"
    if ms < 30:
        return Fore.GREEN + val + Style.RESET_ALL
    if ms <= 100:
        return Fore.YELLOW + val + Style.RESET_ALL
    return Fore.RED + val + Style.RESET_ALL

def colour_download(mbps: float) -> str:
    val = f"{mbps:>6.1f} Mbps"
    if mbps > 50:
        return Fore.GREEN + val + Style.RESET_ALL
    if mbps >= 10:
        return Fore.YELLOW + val + Style.RESET_ALL
    return Fore.RED + val + Style.RESET_ALL

def colour_upload(mbps: float) -> str:
    val = f"{mbps:>6.1f} Mbps"
    if mbps > 20:
        return Fore.GREEN + val + Style.RESET_ALL
    if mbps >= 5:
        return Fore.YELLOW + val + Style.RESET_ALL
    return Fore.RED + val + Style.RESET_ALL


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_ping() -> float:
    latencies = []
    for _ in range(PING_ROUNDS):
        t0 = time.perf_counter()
        r  = requests.head(PING_URL, timeout=TIMEOUT)
        t1 = time.perf_counter()
        r.raise_for_status()
        latencies.append((t1 - t0) * 1000)
    return sum(latencies) / len(latencies)


def test_download() -> float:
    t0   = time.perf_counter()
    r    = requests.get(DOWNLOAD_URL, timeout=TIMEOUT, stream=True)
    r.raise_for_status()
    size = 0
    for chunk in r.iter_content(chunk_size=65536):
        size += len(chunk)
    t1   = time.perf_counter()
    return (size * 8) / ((t1 - t0) * 1_000_000)          # Mbps


def test_upload() -> float:
    data = random.randbytes(10 * 1024 * 1024)             # 10 MB
    size = len(data)
    t0   = time.perf_counter()
    r    = requests.post(
        UPLOAD_URL,
        data=data,
        headers={"Content-Type": "application/octet-stream"},
        timeout=TIMEOUT,
    )
    t1   = time.perf_counter()
    r.raise_for_status()
    return (size * 8) / ((t1 - t0) * 1_000_000)          # Mbps


# ── Main ───────────────────────────────────────────────────────────────────────

def run_test(label: str, fn) -> float | None:
    print(f"\n {Fore.CYAN}Testing {label}...{Style.RESET_ALL}")
    try:
        with Spinner(f"Running {label} test"):
            result = fn()
        return result
    except requests.exceptions.Timeout:
        print(f" {Fore.RED}✖  {label} test timed out after {TIMEOUT}s.{Style.RESET_ALL}")
    except requests.exceptions.ConnectionError as exc:
        print(f" {Fore.RED}✖  Connection error during {label} test: {exc}{Style.RESET_ALL}")
    except requests.exceptions.HTTPError as exc:
        print(f" {Fore.RED}✖  HTTP error during {label} test: {exc}{Style.RESET_ALL}")
    except Exception as exc:
        print(f" {Fore.RED}✖  Unexpected error during {label} test: {exc}{Style.RESET_ALL}")
    return None


def print_results(ping: float | None, dl: float | None, ul: float | None) -> None:
    bar = "=" * 32
    print(f"\n {Fore.WHITE}{Style.BRIGHT}{bar}")
    print(f"   WiFi Speed Test Results")
    print(f" {bar}{Style.RESET_ALL}")

    ping_str = colour_ping(ping)   if ping is not None else Fore.RED + "  ERROR" + Style.RESET_ALL
    dl_str   = colour_download(dl) if dl   is not None else Fore.RED + "  ERROR" + Style.RESET_ALL
    ul_str   = colour_upload(ul)   if ul   is not None else Fore.RED + "  ERROR" + Style.RESET_ALL

    print(f"  Ping      :  {ping_str}")
    print(f"  Download  :  {dl_str}")
    print(f"  Upload    :  {ul_str}")
    print(f" {Fore.WHITE}{Style.BRIGHT}{bar}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    print(f"\n {Fore.WHITE}{Style.BRIGHT}WiFi Speed Test{Style.RESET_ALL}")
    print(f" {Fore.CYAN}Powered by Cloudflare speed.cloudflare.com{Style.RESET_ALL}")

    ping_ms   = run_test("ping",     test_ping)
    dl_mbps   = run_test("download", test_download)
    ul_mbps   = run_test("upload",   test_upload)

    print_results(ping_ms, dl_mbps, ul_mbps)
```
