import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ultimate_agent.agent import agent
from ultimate_agent.config import WORKSPACE_DIR

print("Testing agent live chat and tool execution...")
prompt = "Please create a folder called 'TestProject' in the workspace, and inside it create a file called 'app.py' with the content: print('Ultimate Hermes Agent operational')"
res = agent.chat(prompt)

print("--- RESULT ---")
print("Response text:", res.get("response"))
print("Tool calls made:", res.get("tool_calls"))

target_folder = WORKSPACE_DIR / "TestProject"
target_file = target_folder / "app.py"

print("Folder created:", target_folder.is_dir())
print("File created:", target_file.is_file())
if target_file.is_file():
    print("File content:", target_file.read_text(encoding="utf-8"))
