"""Shared Cinemagoer client instance."""

from __future__ import annotations

from imdb import Cinemagoer

_ia: Cinemagoer | None = None


def get_client() -> Cinemagoer:
    """Return a shared Cinemagoer instance."""
    global _ia
    if _ia is None:
        _ia = Cinemagoer()
    return _ia
