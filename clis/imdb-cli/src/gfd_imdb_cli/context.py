"""Shared CLI context: exit codes and helpers."""

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_AUTH = 3
EXIT_NOT_FOUND = 4


def normalize_id(movie_id: str) -> str:
    """Ensure movie ID has 'tt' prefix for GraphQL lookups."""
    if movie_id.startswith("tt"):
        return movie_id
    return f"tt{movie_id}"
