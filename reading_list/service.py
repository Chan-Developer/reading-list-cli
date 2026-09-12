"""Reading-list operations independent from command-line formatting."""

import json
from pathlib import Path
from typing import Any

from .errors import ImportFileError, ItemNotFoundError, ValidationError
from .storage import JsonStorage
from .validation import validate_title, validate_url


class ReadingListService:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def add(self, title: str, url: str, tags: list[str]) -> dict[str, Any]:
        data = self.storage.load()
        item = {
            "id": data["next_id"],
            "title": validate_title(title),
            "url": validate_url(url),
            "tags": tags,
            "done": False,
        }
        data["items"].append(item)
        data["next_id"] += 1
        self.storage.save(data)
        return item

    def list_items(
        self, status: str = "all", tag: str | None = None
    ) -> list[dict[str, Any]]:
        """Return items filtered by read status and/or an exact tag."""
        items = self.storage.load()["items"]
        if status == "unread":
            items = [item for item in items if not item["done"]]
        elif status == "done":
            items = [item for item in items if item["done"]]
        if tag is not None:
            items = [item for item in items if tag in item["tags"]]
        return sorted(items, key=lambda item: item["id"])

    def import_from_file(self, source_path: str | Path) -> tuple[int, int]:
        """Import valid source items and return ``(imported, skipped)`` counts.

        The complete source is parsed and validated before any local data is
        saved, ensuring a bad import cannot partially modify the reading list.
        """
        source_items = self._load_import_items(Path(source_path))
        data = self.storage.load()
        known_urls = {item["url"] for item in data["items"]}
        imported = 0
        skipped = 0
        for source_item in source_items:
            if source_item["url"] in known_urls:
                skipped += 1
                continue
            data["items"].append(
                {
                    "id": data["next_id"],
                    "title": source_item["title"],
                    "url": source_item["url"],
                    "tags": source_item["tags"],
                    "done": False,
                }
            )
            data["next_id"] += 1
            known_urls.add(source_item["url"])
            imported += 1
        if imported:
            self.storage.save(data)
        return imported, skipped

    def mark_done(self, item_id: int) -> dict[str, Any]:
        data = self.storage.load()
        item = self._find_item(data["items"], item_id)
        item["done"] = True
        self.storage.save(data)
        return item

    def remove(self, item_id: int) -> dict[str, Any]:
        data = self.storage.load()
        item = self._find_item(data["items"], item_id)
        data["items"].remove(item)
        self.storage.save(data)
        return item

    def stats(self) -> tuple[int, int, int]:
        items = self.storage.load()["items"]
        total = len(items)
        completed = sum(item["done"] for item in items)
        return total, completed, total - completed

    @staticmethod
    def _load_import_items(source_path: Path) -> list[dict[str, Any]]:
        try:
            with source_path.open("r", encoding="utf-8") as source_file:
                source_data = json.load(source_file)
        except OSError as error:
            raise ImportFileError(f"Could not read import file '{source_path}': {error}") from error
        except json.JSONDecodeError as error:
            raise ImportFileError(
                f"Import file '{source_path}' contains invalid JSON (line {error.lineno}, "
                f"column {error.colno})."
            ) from error

        if not isinstance(source_data, list):
            raise ImportFileError("Import file must contain a top-level JSON array.")

        validated_items: list[dict[str, Any]] = []
        for index, item in enumerate(source_data):
            if not isinstance(item, dict):
                raise ImportFileError(f"Import item at index {index} must be an object.")
            title = item.get("title")
            if not isinstance(title, str) or not title.strip():
                raise ImportFileError(
                    f"Import item at index {index} must have a non-empty string 'title'."
                )
            url = item.get("url")
            if not isinstance(url, str):
                raise ImportFileError(
                    f"Import item at index {index} must have a string 'url'."
                )
            try:
                cleaned_url = validate_url(url)
            except ValidationError as error:
                raise ImportFileError(f"Import item at index {index}: {error}") from error

            tags = item.get("tags", [])
            if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
                raise ImportFileError(
                    f"Import item at index {index} has invalid 'tags'; it must be an array of strings."
                )
            validated_items.append(
                {"title": title.strip(), "url": cleaned_url, "tags": list(tags)}
            )
        return validated_items

    @staticmethod
    def _find_item(items: list[dict[str, Any]], item_id: int) -> dict[str, Any]:
        for item in items:
            if item["id"] == item_id:
                return item
        raise ItemNotFoundError(f"No reading-list item exists with id {item_id}.")
