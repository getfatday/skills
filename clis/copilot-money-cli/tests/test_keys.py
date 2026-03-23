"""Unit tests for the LevelDB key parser."""

from __future__ import annotations

from gfd_copilot_money_cli.core.keys import _SKIP_TYPES, parse_key


def _make_key(*segments: str, prefix: int = 0x85) -> bytes:
    """Build a synthetic LevelDB key with printable segments separated by 0x00."""
    parts: list[bytes] = [bytes([prefix])]
    for i, seg in enumerate(segments):
        if i > 0:
            parts.append(b"\x00\x01")  # non-printable separator
        parts.append(seg.encode("ascii"))
    parts.append(b"\x00")  # trailing null
    return b"".join(parts)


class TestParseKey:
    def test_parse_remote_document_key(self):
        """Valid remote_document key returns type + path segments."""
        key = _make_key("remote_document", "users", "abc123", "accounts", "def456")
        result = parse_key(key)
        assert result is not None
        key_type, segments = result
        assert key_type == "remote_document"
        assert "users" in segments
        assert "abc123" in segments
        assert "accounts" in segments
        assert "def456" in segments

    def test_parse_collection_parent_key_skipped(self):
        """collection_parent is in _SKIP_TYPES, returns None."""
        key = _make_key("collection_parent", "users", "abc")
        result = parse_key(key)
        assert result is None

    def test_skip_all_metadata_types(self):
        """Every key type in _SKIP_TYPES returns None."""
        for skip_type in _SKIP_TYPES:
            key = _make_key(skip_type, "some", "data")
            result = parse_key(key)
            assert result is None, f"Expected None for {skip_type}"

    def test_empty_key(self):
        """Empty bytes returns None."""
        assert parse_key(b"") is None

    def test_no_printable_ascii(self):
        """All non-printable bytes returns None (no segments extracted)."""
        key = bytes([0x00, 0x01, 0x02, 0x80, 0xFF])
        assert parse_key(key) is None

    def test_key_segments_split_correctly(self):
        """Segments are split on non-printable byte boundaries."""
        key = _make_key("remote_document", "collection_A", "doc123")
        result = parse_key(key)
        assert result is not None
        key_type, segments = result
        assert key_type == "remote_document"
        assert segments == ["collection_A", "doc123"]

    def test_single_segment_key(self):
        """A key with only the type segment and no path segments."""
        # Non-skip type with no path
        key = _make_key("unknown_type")
        result = parse_key(key)
        assert result is not None
        key_type, segments = result
        assert key_type == "unknown_type"
        assert segments == []

    def test_key_with_spaces_in_segment(self):
        """Spaces are printable ASCII (byte 32), so included in segments."""
        key = _make_key("remote_document", "My Account")
        result = parse_key(key)
        assert result is not None
        _, segments = result
        assert "My Account" in segments

    def test_key_with_tildes_and_dashes(self):
        """Special printable chars like ~ (126) and - are kept."""
        key = _make_key("remote_document", "foo-bar~baz")
        result = parse_key(key)
        assert result is not None
        _, segments = result
        assert "foo-bar~baz" in segments

    def test_key_trailing_printable(self):
        """Trailing printable bytes (no null terminator) still captured."""
        key = b"\x85\x00remote_document\x00path_end"
        result = parse_key(key)
        assert result is not None
        key_type, segments = result
        assert key_type == "remote_document"
        assert "path_end" in segments
