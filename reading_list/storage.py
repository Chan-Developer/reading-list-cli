"""JSON persistence for the reading list."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .errors import DataFileError


def empty_data() -> dict[str, Any]:
    return {"next_id": 1, "items": []}


class JsonStorage:
    """Read and atomically write the local JSON data file."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return empty_data()
        try:
            with self.path.open("r", encoding="utf-8") as data_file:
                data = json.load(data_file)
        except OSError as error:
            raise DataFileError(f"Could not read data file '{self.path}': {error}") from error
        except json.JSONDecodeError as error:
            raise DataFileError(
                f"Data file '{self.path}' contains invalid JSON (line {error.lineno}, "
                f"column {error.colno})."
            ) from error
        self._validate_data(data)
        return data

    def save(self, data: dict[str, Any]) -> None:
        self._validate_data(data)
        parent = self.path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.", suffix=".tmp", dir=parent, text=True
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
                    json.dump(data, temporary_file, ensure_ascii=False, indent=2)
                    temporary_file.write("\n")
                os.replace(temporary_name, self.path)
            except Exception:
                try:
                    os.unlink(temporary_name)
                except FileNotFoundError:
                    pass
                raise
        except OSError as error:
            raise DataFileError(f"Could not write data file '{self.path}': {error}") from error

    @staticmethod
    def _validate_data(data: Any) -> None:
        if not isinstance(data, dict) or set(data) != {"next_id", "items"}:
            raise DataFileError(
                "Data file has an invalid format; expected an object with 'next_id' and 'items'."
            )
        if (
            not isinstance(data["next_id"], int)
            or isinstance(data["next_id"], bool)
            or data["next_id"] < 1
        ):
            raise DataFileError("Data file has an invalid 'next_id' value.")
        if not isinstance(data["items"], list):
            raise DataFileError("Data file has an invalid 'items' value; it must be a list.")
        expected_keys = {"id", "title", "url", "tags", "done"}
        seen_ids: set[int] = set()
        for item in data["items"]:
            if not isinstance(item, dict) or set(item) != expected_keys:
                raise DataFileError("Data file contains an item with an invalid format.")
            if (
                not isinstance(item["id"], int)
                or isinstance(item["id"], bool)
                or item["id"] < 1
                or item["id"] in seen_ids
                or not isinstance(item["title"], str)
                or not isinstance(item["url"], str)
                or not isinstance(item["tags"], list)
                or not all(isinstance(tag, str) for tag in item["tags"])
                or not isinstance(item["done"], bool)
            ):
                raise DataFileError("Data file contains an item with invalid values.")
            seen_ids.add(item["id"])
        if seen_ids and data["next_id"] <= max(seen_ids):
            raise DataFileError(
                "Data file has an invalid 'next_id'; it must be greater than every item id."
            )
