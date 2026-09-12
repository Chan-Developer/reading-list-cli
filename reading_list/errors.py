"""Exceptions that should be shown to CLI users."""


class ReadingListError(Exception):
    """Base exception for expected application errors."""


class DataFileError(ReadingListError):
    """The reading-list data file cannot be read safely."""


class ImportFileError(ReadingListError):
    """The file passed to the import command is invalid or unreadable."""


class ValidationError(ReadingListError):
    """User input is invalid."""


class ItemNotFoundError(ReadingListError):
    """A requested item id does not exist."""
