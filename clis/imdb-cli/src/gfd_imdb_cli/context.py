"""Shared CLI context: exit codes and helpers."""

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_AUTH = 3
EXIT_NOT_FOUND = 4


def normalize_id(movie_id: str) -> str:
    """Strip optional 'tt' prefix from IMDB IDs."""
    return movie_id.lstrip("t")
