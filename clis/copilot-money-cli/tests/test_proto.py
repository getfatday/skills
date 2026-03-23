"""Unit tests for the hand-rolled Firestore protobuf parser."""

from __future__ import annotations

import struct

import pytest
from gfd_copilot_money_cli.core.proto import (
    decode_document,
    decode_tag,
    decode_value_from_submsg,
    decode_varint,
    skip_field,
)

# ---------------------------------------------------------------------------
# Helpers — build protobuf wire-format bytes
# ---------------------------------------------------------------------------

def _encode_varint(value: int) -> bytes:
    """Encode an unsigned integer as a protobuf varint."""
    parts: list[int] = []
    while value > 0x7F:
        parts.append((value & 0x7F) | 0x80)
        value >>= 7
    parts.append(value & 0x7F)
    return bytes(parts)


def _encode_tag(field_number: int, wire_type: int) -> bytes:
    return _encode_varint((field_number << 3) | wire_type)


def _length_delimited(field_number: int, payload: bytes) -> bytes:
    """Encode a length-delimited field (wire type 2)."""
    return _encode_tag(field_number, 2) + _encode_varint(len(payload)) + payload


def _varint_field(field_number: int, value: int) -> bytes:
    """Encode a varint field (wire type 0)."""
    return _encode_tag(field_number, 0) + _encode_varint(value)


def _fixed64_field(field_number: int, double_value: float) -> bytes:
    """Encode a fixed64 field (wire type 1) holding a double."""
    return _encode_tag(field_number, 1) + struct.pack("<d", double_value)


# ---------------------------------------------------------------------------
# decode_varint
# ---------------------------------------------------------------------------

class TestDecodeVarint:
    def test_decode_varint_simple(self):
        """Single-byte varint: 0x05 -> 5."""
        val, pos = decode_varint(b"\x05", 0)
        assert val == 5
        assert pos == 1

    def test_decode_varint_multibyte(self):
        """Multi-byte varint: 300 = 0xAC 0x02."""
        val, pos = decode_varint(b"\xac\x02", 0)
        assert val == 300
        assert pos == 2

    def test_decode_varint_zero(self):
        val, pos = decode_varint(b"\x00", 0)
        assert val == 0
        assert pos == 1

    def test_decode_varint_max_single_byte(self):
        """127 = 0x7F, single byte."""
        val, pos = decode_varint(b"\x7f", 0)
        assert val == 127
        assert pos == 1

    def test_decode_varint_negative(self):
        """Two's complement 64-bit: -1 is 10 bytes of 0xFF ending 0x01."""
        # unsigned representation of -1 in 64-bit two's complement
        unsigned_neg1 = (1 << 64) - 1
        encoded = _encode_varint(unsigned_neg1)
        val, pos = decode_varint(encoded, 0)
        assert val == unsigned_neg1
        assert pos == len(encoded)

    def test_decode_varint_truncated(self):
        """Truncated varint raises ValueError."""
        with pytest.raises(ValueError, match="Truncated varint"):
            decode_varint(b"\x80", 0)  # continuation bit set, no more bytes

    def test_decode_varint_at_offset(self):
        """Decoding starts at the given position, not byte 0."""
        buf = b"\xff\x05"  # junk byte then varint 5
        val, pos = decode_varint(buf, 1)
        assert val == 5
        assert pos == 2


# ---------------------------------------------------------------------------
# decode_tag
# ---------------------------------------------------------------------------

class TestDecodeTag:
    def test_decode_tag(self):
        """Field 2, wire type 0 -> tag byte = (2 << 3) | 0 = 0x10."""
        field, wt, pos = decode_tag(b"\x10", 0)
        assert field == 2
        assert wt == 0
        assert pos == 1

    def test_decode_tag_field_17_wire2(self):
        """Field 17, wire type 2 -> tag = (17 << 3) | 2 = 0x8A 0x01."""
        tag_bytes = _encode_tag(17, 2)
        field, wt, pos = decode_tag(tag_bytes, 0)
        assert field == 17
        assert wt == 2

    def test_decode_tag_field_1_wire0(self):
        """Field 1, wire type 0 -> tag byte = 0x08."""
        field, wt, pos = decode_tag(b"\x08", 0)
        assert field == 1
        assert wt == 0


# ---------------------------------------------------------------------------
# skip_field
# ---------------------------------------------------------------------------

class TestSkipField:
    def test_skip_varint(self):
        buf = b"\x05"  # varint 5
        new_pos = skip_field(buf, 0, 0)
        assert new_pos == 1

    def test_skip_fixed64(self):
        buf = b"\x00" * 8
        new_pos = skip_field(buf, 0, 1)
        assert new_pos == 8

    def test_skip_length_delimited(self):
        payload = b"hello"
        buf = _encode_varint(len(payload)) + payload
        new_pos = skip_field(buf, 0, 2)
        assert new_pos == len(buf)

    def test_skip_fixed32(self):
        buf = b"\x00" * 4
        new_pos = skip_field(buf, 0, 5)
        assert new_pos == 4

    def test_skip_unknown_wire_type(self):
        with pytest.raises(ValueError, match="Unknown wire type"):
            skip_field(b"\x00", 0, 3)


# ---------------------------------------------------------------------------
# decode_value_from_submsg — Firestore value types
# ---------------------------------------------------------------------------

class TestDecodeValue:
    def test_decode_string(self):
        """Field 17, wire type 2 = Firestore string value."""
        payload = b"hello"
        buf = _length_delimited(17, payload)
        val, _ = decode_value_from_submsg(buf, 0, len(buf))
        assert val == "hello"

    def test_decode_boolean_true(self):
        """Field 1, wire type 0 = boolean."""
        buf = _varint_field(1, 1)
        val, _ = decode_value_from_submsg(buf, 0, len(buf))
        assert val is True

    def test_decode_boolean_false(self):
        buf = _varint_field(1, 0)
        val, _ = decode_value_from_submsg(buf, 0, len(buf))
        assert val is False

    def test_decode_integer(self):
        """Field 2, wire type 0 = integer."""
        buf = _varint_field(2, 42)
        val, _ = decode_value_from_submsg(buf, 0, len(buf))
        assert val == 42

    def test_decode_integer_negative(self):
        """Negative integer via two's complement."""
        unsigned = (1 << 64) - 5  # represents -5
        buf = _varint_field(2, unsigned)
        val, _ = decode_value_from_submsg(buf, 0, len(buf))
        assert val == -5

    def test_decode_double(self):
        """Field 3, wire type 1 = double (fixed64)."""
        buf = _fixed64_field(3, 3.14)
        val, _ = decode_value_from_submsg(buf, 0, len(buf))
        assert abs(val - 3.14) < 1e-10

    def test_decode_null(self):
        """Field 11, wire type 0 = null."""
        buf = _varint_field(11, 0)
        val, _ = decode_value_from_submsg(buf, 0, len(buf))
        assert val is None

    def test_decode_timestamp(self):
        """Field 10, wire type 2 = timestamp sub-message with seconds + nanos."""
        # Timestamp: field 1 = seconds, field 2 = nanos
        ts_inner = _varint_field(1, 1700000000) + _varint_field(2, 500000000)
        buf = _length_delimited(10, ts_inner)
        val, _ = decode_value_from_submsg(buf, 0, len(buf))
        # Should be an ISO 8601 string
        assert isinstance(val, str)
        assert "2023-11-14" in val

    def test_decode_array(self):
        """Field 9, wire type 2 = array of values."""
        # Array contains repeated field 1 = Value sub-messages
        # Two string values
        elem1 = _length_delimited(17, b"alpha")
        elem2 = _length_delimited(17, b"beta")
        array_inner = _length_delimited(1, elem1) + _length_delimited(1, elem2)
        buf = _length_delimited(9, array_inner)
        val, _ = decode_value_from_submsg(buf, 0, len(buf))
        assert val == ["alpha", "beta"]

    def test_decode_map(self):
        """Field 6, wire type 2 = map value."""
        # MapValue: repeated field 1 = MapEntry
        # MapEntry: field 1 = key (string), field 2 = Value
        key_field = _length_delimited(1, b"color")
        val_field = _length_delimited(2, _length_delimited(17, b"red"))
        entry = key_field + val_field
        map_inner = _length_delimited(1, entry)
        buf = _length_delimited(6, map_inner)
        val, _ = decode_value_from_submsg(buf, 0, len(buf))
        assert val == {"color": "red"}


# ---------------------------------------------------------------------------
# decode_document
# ---------------------------------------------------------------------------

class TestDecodeDocument:
    def test_decode_document_empty(self):
        """Empty bytes returns None."""
        assert decode_document(b"") is None

    def test_decode_document_none_input(self):
        """None-ish empty bytes returns None."""
        assert decode_document(b"") is None

    def test_decode_document_malformed(self):
        """Malformed bytes returns None (caught by except)."""
        assert decode_document(b"\xff\xff\xff") is None

    def test_decode_document_no_field2(self):
        """Valid protobuf but no field 2 (Document) returns None."""
        # Field 1, wire type 0, value 1 — not a Document field
        buf = _varint_field(1, 1)
        assert decode_document(buf) is None

    def test_decode_document_minimal(self):
        """Minimal valid MaybeDocument: field 2 = Document with one MapEntry."""
        # Build a Document with one field: "name" = "test"
        key_field = _length_delimited(1, b"name")
        val_field = _length_delimited(2, _length_delimited(17, b"test"))
        map_entry = key_field + val_field
        document = _length_delimited(2, map_entry)  # Document field 2 = MapEntry
        maybe_doc = _length_delimited(2, document)   # MaybeDocument field 2 = Document
        result = decode_document(maybe_doc)
        assert result is not None
        assert result["name"] == "test"
