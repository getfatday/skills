"""Binary key parser for Copilot Money's LevelDB cache.

Keys start with byte 0x85 and contain readable ASCII strings separated
by non-printable binary markers. The first string identifies the key type
(e.g. "remote_document"), and subsequent strings form the Firestore path.
"""

from __future__ import annotations

# Metadata key types we skip entirely
_SKIP_TYPES = frozenset({
    "collection_parent",
    "target",
    "target_global",
    "mutation_queue",
    "document_target",
    "remote_document_read_time",
    "target_document",
    "query_target",
    "version",
})


def parse_key(key_bytes: bytes) -> tuple[str, list[str]] | None:
    """Parse a LevelDB key into (key_type, path_segments).

    Returns None if the key is unparseable or is a metadata key type
    we don't care about.
    """
    if not key_bytes:
        return None

    # Extract runs of printable ASCII characters (bytes 32-126)
    segments: list[str] = []
    current: list[int] = []

    for b in key_bytes:
        if 32 <= b <= 126:
            current.append(b)
        else:
            if current:
                segments.append(bytes(current).decode("ascii"))
                current = []
    if current:
        segments.append(bytes(current).decode("ascii"))

    if not segments:
        return None

    key_type = segments[0]
    path_segments = segments[1:]

    if key_type in _SKIP_TYPES:
        return None

    return key_type, path_segments
