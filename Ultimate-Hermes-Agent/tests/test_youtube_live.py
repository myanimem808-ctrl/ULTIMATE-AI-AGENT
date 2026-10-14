import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ultimate_agent.youtube import analyze, get_job, start_download

test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw" # Me at the zoo (short, 19 sec)

print("1. Testing YouTube analyze...")
info = analyze(test_url)
print(f"Title: {info.get('title')}")
print(f"Resolutions found: {info.get('resolutions')}")
assert info.get("title"), "Should have title"

print("\n2. Testing YouTube dual-engine download with auto fallback...")
job = start_download(test_url, quality="360", output_format="mp4", engine="auto")
print(f"Queued job id: {job['id']}, engine: {job['engine_requested']}")

for _ in range(30):
    time.sleep(1)
    status = get_job(job["id"])
    if status["status"] in {"completed", "failed"}:
        print(f"Final status: {status['status']}")
        print(f"Engine used: {status.get('engine_used')}")
        print(f"Fallback triggered: {status.get('fallback_triggered')}")
        print(f"Output file: {status.get('file_name')}")
        if status.get("error"):
            print(f"Error: {status.get('error')}")
        assert status["status"] == "completed", f"Download failed: {status.get('error')}"
        break
    else:
        print(f"Progress: {status.get('progress')}% ({status.get('status')})")

print("\nYouTube Dual-Engine Download Test PASSED!")
