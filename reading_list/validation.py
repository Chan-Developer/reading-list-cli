"""Validation and normalisation helpers."""

from urllib.parse import urlparse

from .errors import ValidationError


def validate_title(title: str) -> str:
    """Return a trimmed non-empty title."""
    cleaned = title.strip()
    if not cleaned:
        raise ValidationError("Title cannot be empty.")
    return cleaned


def validate_url(url: str) -> str:
    """Return a URL restricted to normal web links."""
    cleaned = url.strip()
    try:
        parsed = urlparse(cleaned)
        parsed.port
    except ValueError as error:
        raise ValidationError(
            "Invalid URL. Use a complete http:// or https:// URL with a valid port."
        ) from error
    if (
        not cleaned
        or any(character.isspace() for character in cleaned)
        or parsed.scheme not in {"http", "https"}
        or not parsed.netloc
    ):
        raise ValidationError(
            "Invalid URL. Use a complete http:// or https:// URL, for example "
            "https://example.com/article."
        )
    return cleaned


def parse_tags(raw_tags: str | None) -> list[str]:
    """Convert a comma-separated tag option into unique, trimmed tags."""
    if raw_tags is None:
        return []
    tags: list[str] = []
    for tag in raw_tags.split(","):
        cleaned = tag.strip()
        if cleaned and cleaned not in tags:
            tags.append(cleaned)
    return tags
