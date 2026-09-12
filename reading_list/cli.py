"""Command-line interface for the reading-list manager."""

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .errors import ReadingListError
from .service import ReadingListService
from .storage import JsonStorage
from .validation import parse_tags


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reading-list", description="Manage a local list of articles to read."
    )
    parser.add_argument(
        "--data-file",
        default=".reading_list.json",
        metavar="PATH",
        help="JSON data file (default: .reading_list.json)",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    add_parser = commands.add_parser("add", help="Add an article")
    add_parser.add_argument("title", help="Article title")
    add_parser.add_argument("url", help="Article URL (http or https)")
    add_parser.add_argument("--tags", metavar="TAG[,TAG...]", help="Comma-separated tags")

    list_parser = commands.add_parser("list", help="List articles")
    list_parser.add_argument(
        "--status",
        choices=("all", "unread", "done"),
        default="all",
        help="Filter by status (default: all)",
    )
    list_parser.add_argument("--tag", metavar="TAG", help="Filter by an exact tag")

    import_parser = commands.add_parser("import", help="Import articles from a JSON array")
    import_parser.add_argument("file", metavar="FILE", help="Source JSON file")

    done_parser = commands.add_parser("done", help="Mark an article as read")
    done_parser.add_argument("id", type=positive_id, help="Item id")

    remove_parser = commands.add_parser("remove", help="Remove an article")
    remove_parser.add_argument("id", type=positive_id, help="Item id")

    commands.add_parser("stats", help="Show reading-list totals")
    return parser


def positive_id(value: str) -> int:
    try:
        item_id = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("id must be a positive integer") from error
    if item_id < 1:
        raise argparse.ArgumentTypeError("id must be a positive integer")
    return item_id


def format_item(item: dict) -> str:
    status = "done" if item["done"] else "todo"
    tags = f" | tags: {', '.join(item['tags'])}" if item["tags"] else ""
    return f"[{item['id']}] {status} | {item['title']} | {item['url']}{tags}"


def main(arguments: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(arguments)
    service = ReadingListService(JsonStorage(Path(args.data_file)))
    try:
        if args.command == "add":
            item = service.add(args.title, args.url, parse_tags(args.tags))
            print(f"Added item {item['id']}: {item['title']}")
        elif args.command == "list":
            items = service.list_items(status=args.status, tag=args.tag)
            if not items:
                print("No matching reading-list items.")
            else:
                for item in items:
                    print(format_item(item))
        elif args.command == "import":
            imported, skipped = service.import_from_file(args.file)
            print(f"Imported: {imported}")
            print(f"Skipped: {skipped}")
        elif args.command == "done":
            item = service.mark_done(args.id)
            print(f"Marked item {item['id']} as done: {item['title']}")
        elif args.command == "remove":
            item = service.remove(args.id)
            print(f"Removed item {item['id']}: {item['title']}")
        elif args.command == "stats":
            total, completed, remaining = service.stats()
            print(f"Total: {total}")
            print(f"Done: {completed}")
            print(f"To read: {remaining}")
    except ReadingListError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0
