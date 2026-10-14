import tempfile
import unittest
from pathlib import Path

from ultimate_agent.file_memory import FileMemory


class FileMemoryTests(unittest.TestCase):
    def test_index_and_search_text_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "documents"
            root.mkdir()
            source = root / "notes.md"
            source.write_text("Hermes keeps persistent context with a custom keyword: silver-orbit.", encoding="utf-8")
            memory = FileMemory(Path(tmp) / "memory.sqlite3")
            report = memory.index_folder(str(root))
            self.assertEqual(report["indexed_or_updated"], 1)
            results = memory.search("silver-orbit", limit=5)
            self.assertTrue(results)
            self.assertIn("silver-orbit", results[0]["excerpt"])
            self.assertEqual(memory.stats()["indexed_files"], 1)

    def test_skips_env_credential_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "documents"
            root.mkdir()
            (root / "notes.txt").write_text("safe searchable note", encoding="utf-8")
            (root / ".env").write_text("SECRET_TOKEN=should-not-be-indexed", encoding="utf-8")
            memory = FileMemory(Path(tmp) / "memory.sqlite3")
            memory.index_folder(str(root))
            self.assertFalse(memory.search("should-not-be-indexed"))
            self.assertEqual(memory.stats()["indexed_files"], 1)

    def test_archive_inventory_rejects_non_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "not-a-zip.txt"
            file_path.write_text("plain text", encoding="utf-8")
            memory = FileMemory(Path(tmp) / "memory.sqlite3")
            with self.assertRaises(ValueError):
                memory.analyze_archive(str(file_path))


if __name__ == "__main__":
    unittest.main()
