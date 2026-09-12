import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from reading_list.cli import main, parse_tags
from reading_list.errors import (
    DataFileError,
    ImportFileError,
    ItemNotFoundError,
    ValidationError,
)
from reading_list.service import ReadingListService
from reading_list.storage import JsonStorage
from reading_list.validation import validate_title, validate_url


class ReadingListServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.data_path = Path(self.temporary_directory.name) / "list.json"
        self.service = ReadingListService(JsonStorage(self.data_path))

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_add_persists_item_with_incrementing_id(self):
        first = self.service.add("First", "https://example.com/one", ["python"])
        second = self.service.add("Second", "https://example.com/two", [])

        self.assertEqual(first["id"], 1)
        self.assertEqual(second["id"], 2)
        self.assertEqual([item["title"] for item in self.service.list_items()], ["First", "Second"])

    def test_done_updates_stats(self):
        item = self.service.add("First", "https://example.com", [])
        self.service.mark_done(item["id"])

        self.assertEqual(self.service.stats(), (1, 1, 0))
        self.assertTrue(self.service.list_items()[0]["done"])

    def test_remove_deletes_only_requested_item(self):
        first = self.service.add("First", "https://example.com/one", [])
        self.service.add("Second", "https://example.com/two", [])

        removed = self.service.remove(first["id"])

        self.assertEqual(removed["title"], "First")
        self.assertEqual([item["id"] for item in self.service.list_items()], [2])

    def test_unknown_id_raises_clear_exception(self):
        with self.assertRaises(ItemNotFoundError):
            self.service.mark_done(99)
        with self.assertRaises(ItemNotFoundError):
            self.service.remove(99)

    def write_import_file(self, data):
        import_path = Path(self.temporary_directory.name) / "import.json"
        import_path.write_text(json.dumps(data), encoding="utf-8")
        return import_path

    def test_import_successfully_adds_unread_items(self):
        import_path = self.write_import_file(
            [
                {"title": "One", "url": "https://example.com/one", "tags": ["python"]},
                {"title": "Two", "url": "https://example.com/two"},
            ]
        )

        self.assertEqual(self.service.import_from_file(import_path), (2, 0))
        self.assertEqual(
            self.service.list_items(),
            [
                {
                    "id": 1,
                    "title": "One",
                    "url": "https://example.com/one",
                    "tags": ["python"],
                    "done": False,
                },
                {
                    "id": 2,
                    "title": "Two",
                    "url": "https://example.com/two",
                    "tags": [],
                    "done": False,
                },
            ],
        )

    def test_invalid_import_is_atomic_and_reports_its_index(self):
        existing = self.service.add("Existing", "https://example.com/existing", [])
        before_contents = self.data_path.read_text(encoding="utf-8")
        import_path = self.write_import_file(
            [
                {"title": "Valid", "url": "https://example.com/valid"},
                {"title": "Bad URL", "url": "not a url"},
            ]
        )

        with self.assertRaisesRegex(ImportFileError, "index 1"):
            self.service.import_from_file(import_path)

        self.assertEqual(self.data_path.read_text(encoding="utf-8"), before_contents)
        self.assertEqual(self.service.list_items(), [existing])

    def test_import_skips_existing_and_in_file_duplicate_urls(self):
        self.service.add("Existing", "https://example.com/existing", [])
        import_path = self.write_import_file(
            [
                {"title": "Duplicate existing", "url": "https://example.com/existing"},
                {"title": "New", "url": "https://example.com/new", "tags": ["web"]},
                {"title": "Duplicate new", "url": "https://example.com/new"},
            ]
        )

        self.assertEqual(self.service.import_from_file(import_path), (1, 2))
        self.assertEqual(
            [item["url"] for item in self.service.list_items()],
            ["https://example.com/existing", "https://example.com/new"],
        )

    def test_list_combines_status_and_tag_filters_in_id_order(self):
        first = self.service.add("Unread Python", "https://example.com/one", ["python"])
        second = self.service.add("Done Python", "https://example.com/two", ["python"])
        self.service.add("Done Web", "https://example.com/three", ["web"])
        self.service.mark_done(second["id"])
        self.service.mark_done(3)

        items = self.service.list_items(status="done", tag="python")

        self.assertEqual([item["id"] for item in items], [second["id"]])
        self.assertNotIn(first["id"], [item["id"] for item in items])


class ValidationTests(unittest.TestCase):
    def test_url_requires_http_or_https_with_host(self):
        for invalid_url in (
            "example.com",
            "ftp://example.com",
            "https:///path",
            "https://bad url",
            "https://example.com:badport",
        ):
            with self.subTest(invalid_url=invalid_url):
                with self.assertRaises(ValidationError):
                    validate_url(invalid_url)

    def test_url_allows_numeric_port(self):
        self.assertEqual(
            validate_url("https://example.com:8443/article"),
            "https://example.com:8443/article",
        )

    def test_title_cannot_be_blank(self):
        with self.assertRaises(ValidationError):
            validate_title("   ")

    def test_tags_are_trimmed_and_deduplicated(self):
        self.assertEqual(parse_tags(" python, cli,python, , "), ["python", "cli"])


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.data_path = Path(self.temporary_directory.name) / "list.json"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_missing_file_loads_as_empty_list(self):
        self.assertEqual(JsonStorage(self.data_path).load(), {"next_id": 1, "items": []})

    def test_invalid_json_is_reported(self):
        self.data_path.write_text("{not json", encoding="utf-8")
        with self.assertRaisesRegex(DataFileError, "invalid JSON"):
            JsonStorage(self.data_path).load()

    def test_invalid_schema_is_reported(self):
        self.data_path.write_text(json.dumps({"items": []}), encoding="utf-8")
        with self.assertRaisesRegex(DataFileError, "invalid format"):
            JsonStorage(self.data_path).load()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.data_path = str(Path(self.temporary_directory.name) / "list.json")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def run_cli(self, *arguments):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            status = main(["--data-file", self.data_path, *arguments])
        return status, output.getvalue(), errors.getvalue()

    def test_add_list_done_remove_and_stats(self):
        status, output, errors = self.run_cli(
            "add", "Example", "https://example.com", "--tags", "test, web"
        )
        self.assertEqual((status, errors), (0, ""))
        self.assertIn("Added item 1", output)

        status, output, _ = self.run_cli("list")
        self.assertEqual(status, 0)
        self.assertIn("[1] todo", output)
        self.assertIn("tags: test, web", output)

        status, output, _ = self.run_cli("done", "1")
        self.assertEqual(status, 0)
        self.assertIn("Marked item 1 as done", output)

        status, output, _ = self.run_cli("stats")
        self.assertEqual(status, 0)
        self.assertIn("Total: 1", output)
        self.assertIn("Done: 1", output)
        self.assertIn("To read: 0", output)

        status, output, _ = self.run_cli("remove", "1")
        self.assertEqual(status, 0)
        self.assertIn("Removed item 1", output)

    def test_user_errors_return_nonzero(self):
        status, _, errors = self.run_cli("add", "Example", "not-a-url")
        self.assertEqual(status, 1)
        self.assertIn("Invalid URL", errors)

        status, _, errors = self.run_cli("done", "99")
        self.assertEqual(status, 1)
        self.assertIn("No reading-list item exists with id 99", errors)

    def test_damaged_json_returns_nonzero(self):
        Path(self.data_path).write_text("{ damaged", encoding="utf-8")
        status, _, errors = self.run_cli("list")
        self.assertEqual(status, 1)
        self.assertIn("contains invalid JSON", errors)

    def test_import_command_reports_counts(self):
        import_path = Path(self.temporary_directory.name) / "articles.json"
        import_path.write_text(
            json.dumps(
                [
                    {"title": "Imported", "url": "https://example.com/imported"},
                    {"title": "Duplicate", "url": "https://example.com/imported"},
                ]
            ),
            encoding="utf-8",
        )

        status, output, errors = self.run_cli("import", str(import_path))

        self.assertEqual((status, errors), (0, ""))
        self.assertIn("Imported: 1", output)
        self.assertIn("Skipped: 1", output)

    def test_unknown_list_status_is_an_argparse_error(self):
        errors = io.StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit) as context:
            main(["--data-file", self.data_path, "list", "--status", "later"])
        self.assertEqual(context.exception.code, 2)
        self.assertIn("invalid choice", errors.getvalue())

    def test_missing_required_value_exits_nonzero(self):
        errors = io.StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit) as context:
            main(["--data-file", self.data_path, "add", "Only a title"])
        self.assertEqual(context.exception.code, 2)
        self.assertIn("the following arguments are required: url", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
