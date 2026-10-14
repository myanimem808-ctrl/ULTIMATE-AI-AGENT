import os
import tempfile
import unittest
from pathlib import Path

from ultimate_agent.folder_tools import (
    analyze_document,
    compress_item,
    copy_item,
    create_file,
    create_folder,
    delete_item,
    edit_file,
    list_directory,
    move_item,
    read_file,
    rename_item,
    write_file,
)


class FolderToolsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_folder_and_file(self):
        folder_path = str(self.test_dir / "my_project")
        res_folder = create_folder(folder_path)
        self.assertTrue(res_folder["ok"])
        self.assertTrue(Path(folder_path).is_dir())

        file_path = str(self.test_dir / "my_project" / "program.py")
        content = "print('Hello Ultimate Hermes Agent')\n"
        res_file = create_file(file_path, content)
        self.assertTrue(res_file["ok"])
        self.assertTrue(Path(file_path).is_file())

        # read_file
        res_read = read_file(file_path)
        self.assertTrue(res_read["ok"])
        self.assertIn("Hello Ultimate Hermes Agent", res_read["content"])

        # edit_file
        res_edit = edit_file(file_path, "Hello Ultimate Hermes Agent", "Agent running smoothly")
        self.assertTrue(res_edit["ok"])
        self.assertIn("Agent running smoothly", Path(file_path).read_text(encoding="utf-8"))

    def test_list_and_sort_directory(self):
        sub = self.test_dir / "sort_test"
        sub.mkdir()
        (sub / "a.txt").write_text("short", encoding="utf-8")
        (sub / "b.txt").write_text("a very long text content here", encoding="utf-8")
        (sub / "c.log").write_text("log", encoding="utf-8")

        res_list = list_directory(str(sub), sort_by="size")
        self.assertTrue(res_list["ok"])
        self.assertEqual(res_list["total_items"], 3)
        # b.txt should be first when sorted by size descending
        self.assertEqual(res_list["items"][0]["name"], "b.txt")

    def test_move_copy_rename_delete(self):
        src = self.test_dir / "sample.txt"
        src.write_text("sample content", encoding="utf-8")

        # Copy
        cp = self.test_dir / "sample_copy.txt"
        res_copy = copy_item(str(src), str(cp))
        self.assertTrue(res_copy["ok"])
        self.assertTrue(cp.is_file())

        # Rename
        res_ren = rename_item(str(cp), "renamed.txt")
        self.assertTrue(res_ren["ok"])
        renamed = self.test_dir / "renamed.txt"
        self.assertTrue(renamed.is_file())

        # Delete
        res_del = delete_item(str(renamed))
        self.assertTrue(res_del["ok"])
        self.assertFalse(renamed.exists())

    def test_compress_item(self):
        folder = self.test_dir / "to_zip"
        folder.mkdir()
        (folder / "file.txt").write_text("test", encoding="utf-8")

        res_zip = compress_item(str(folder), format="zip")
        self.assertTrue(res_zip["ok"])
        self.assertTrue(Path(res_zip["archive_path"]).is_file())

    def test_analyze_document(self):
        doc = self.test_dir / "notes.txt"
        doc.write_text("Important architectural specification for Ultimate Agent", encoding="utf-8")
        res_doc = analyze_document(str(doc))
        self.assertTrue(res_doc["ok"])
        self.assertIn("Important architectural specification", res_doc["content_excerpt"])


if __name__ == "__main__":
    unittest.main()
