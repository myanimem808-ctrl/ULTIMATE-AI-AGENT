import unittest

from ultimate_agent.system_tools import read_skill, run_command
from ultimate_agent.tools import registry


class SystemToolsTests(unittest.TestCase):
    def test_run_command(self):
        res = run_command("echo Hello from Ultimate Agent")
        self.assertTrue(res["ok"])
        self.assertIn("Hello from Ultimate Agent", res["stdout"])

    def test_read_bundled_skill(self):
        # Hermes has skills like 'web-search' or 'weather' or 'doc' etc.
        res = read_skill("arxiv")
        self.assertTrue(res["ok"])
        self.assertTrue(len(res["instructions"]) > 0)

    def test_registry_contains_unified_tools(self):
        defs = registry.definitions(include_mcp=False)
        names = {t["name"] for t in defs}
        expected = {
            "create_folder", "create_file", "read_file", "write_file",
            "edit_file", "move_item", "copy_item", "rename_item", "delete_item",
            "compress_item", "list_directory", "analyze_document",
            "youtube_analyze", "youtube_download", "run_command", "web_search",
            "web_fetch", "windows_list_windows", "windows_list_processes",
            "windows_take_screenshot", "windows_clipboard_get", "windows_clipboard_set",
            "windows_open_app", "list_agent_skills", "read_skill",
            "file_search", "file_index_folder", "zip_archive_inventory",
        }
        for exp in expected:
            self.assertIn(exp, names)


if __name__ == "__main__":
    unittest.main()
