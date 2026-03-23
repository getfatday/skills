"""Hand-rolled Firestore protobuf parser.

Parses the protobuf wire format without any protobuf library dependency.
Handles the MaybeDocument -> Document -> MapEntry -> Value chain used
by Firestore's local cache.

Wire types:
    0 = varint
    1 = fixed64 (8 bytes)
    2 = length-delimited
    5 = fixed32 (4 bytes)
"""

from __future__ import annotations

import struct
from datetime import datetime, timezone
from typing import Any


def decode_varint(buf: bytes, pos: int) -> tuple[int, int]:
    """Decode a protobuf varint starting at pos.

    Returns (value, new_pos).
    """
    result = 0
    shift = 0
    while pos < len(buf):
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            return result, pos
        shift += 7
    raise ValueError("Truncated varint")


def decode_tag(buf: bytes, pos: int) -> tuple[int, int, int]:
    """Decode a protobuf tag into (field_number, wire_type, new_pos)."""
    tag, pos = decode_varint(buf, pos)
    field_number = tag >> 3
    wire_type = tag & 0x07
    return field_number, wire_type, pos


def skip_field(buf: bytes, pos: int, wire_type: int) -> int:
    """Skip over an unknown field and return new position."""
    if wire_type == 0:  # varint
        _, pos = decode_varint(buf, pos)
    elif wire_type == 1:  # fixed64
        pos += 8
    elif wire_type == 2:  # length-delimited
        length, pos = decode_varint(buf, pos)
        pos += length
    elif wire_type == 5:  # fixed32
        pos += 4
    else:
        raise ValueError(f"Unknown wire type {wire_type}")
    return pos


def _decode_signed_int64(value: int) -> int:
    """Convert an unsigned varint to a signed 64-bit integer (two's complement)."""
    if value >= (1 << 63):
        value -= 1 << 64
    return value


def _decode_timestamp(buf: bytes, pos: int, end: int) -> str:
    """Decode a Firestore Timestamp sub-message into an ISO 8601 string.

    Timestamp has:
        field 1 = seconds (varint)
        field 2 = nanos (varint)
    """
    seconds = 0
    nanos = 0
    while pos < end:
        field_number, wire_type, pos = decode_tag(buf, pos)
        if field_number == 1 and wire_type == 0:
            seconds, pos = decode_varint(buf, pos)
            seconds = _decode_signed_int64(seconds)
        elif field_number == 2 and wire_type == 0:
            nanos, pos = decode_varint(buf, pos)
        else:
            pos = skip_field(buf, pos, wire_type)
    try:
        dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
        if nanos:
            dt = dt.replace(microsecond=nanos // 1000)
        return dt.isoformat()
    except (OSError, OverflowError, ValueError):
        return f"{seconds}.{nanos}"


def _decode_array(buf: bytes, pos: int, end: int) -> list[Any]:
    """Decode a Firestore ArrayValue sub-message.

    ArrayValue has repeated field 1 = Value.
    """
    items: list[Any] = []
    while pos < end:
        field_number, wire_type, pos = decode_tag(buf, pos)
        if field_number == 1 and wire_type == 2:
            length, pos = decode_varint(buf, pos)
            val, _ = decode_value_from_submsg(buf, pos, pos + length)
            items.append(val)
            pos += length
        else:
            pos = skip_field(buf, pos, wire_type)
    return items


def _decode_map(buf: bytes, pos: int, end: int) -> dict[str, Any]:
    """Decode a Firestore MapValue sub-message.

    MapValue has repeated field 1 = MapEntry (same as Document fields).
    """
    result: dict[str, Any] = {}
    while pos < end:
        field_number, wire_type, pos = decode_tag(buf, pos)
        if field_number == 1 and wire_type == 2:
            length, pos = decode_varint(buf, pos)
            entry_end = pos + length
            key, val = _decode_map_entry(buf, pos, entry_end)
            if key is not None:
                result[key] = val
            pos = entry_end
        else:
            pos = skip_field(buf, pos, wire_type)
    return result


def _decode_map_entry(buf: bytes, pos: int, end: int) -> tuple[str | None, Any]:
    """Decode a MapEntry sub-message.

    MapEntry has:
        field 1 = key (string)
        field 2 = Value (Firestore Value oneof)
    """
    key: str | None = None
    value: Any = None
    while pos < end:
        field_number, wire_type, pos = decode_tag(buf, pos)
        if field_number == 1 and wire_type == 2:
            length, pos = decode_varint(buf, pos)
            key = buf[pos : pos + length].decode("utf-8", errors="replace")
            pos += length
        elif field_number == 2 and wire_type == 2:
            length, pos = decode_varint(buf, pos)
            value, _ = decode_value_from_submsg(buf, pos, pos + length)
            pos += length
        else:
            pos = skip_field(buf, pos, wire_type)
    return key, value


def decode_value_from_submsg(buf: bytes, pos: int, end: int) -> tuple[Any, int]:
    """Decode a Firestore Value from a sub-message region.

    The Value is a oneof with these field numbers:
        1  = boolean (varint)
        2  = integer (varint, signed)
        3  = double (fixed64)
        5  = reference (string)
        6  = map (MapValue)
        8  = geopoint (sub-message)
        9  = array (ArrayValue)
        10 = timestamp (sub-message)
        11 = null (varint)
        17 = string (length-delimited)
        18 = bytes (length-delimited)
    """
    value: Any = None
    while pos < end:
        field_number, wire_type, pos = decode_tag(buf, pos)

        if field_number == 1 and wire_type == 0:
            # boolean
            val, pos = decode_varint(buf, pos)
            value = bool(val)
        elif field_number == 2 and wire_type == 0:
            # integer (signed 64-bit)
            val, pos = decode_varint(buf, pos)
            value = _decode_signed_int64(val)
        elif field_number == 3 and wire_type == 1:
            # double (fixed64)
            value = struct.unpack_from("<d", buf, pos)[0]
            pos += 8
        elif field_number == 5 and wire_type == 2:
            # reference string
            length, pos = decode_varint(buf, pos)
            value = buf[pos : pos + length].decode("utf-8", errors="replace")
            pos += length
        elif field_number == 6 and wire_type == 2:
            # map
            length, pos = decode_varint(buf, pos)
            value = _decode_map(buf, pos, pos + length)
            pos += length
        elif field_number == 8 and wire_type == 2:
            # geopoint — decode as dict with latitude/longitude
            length, pos = decode_varint(buf, pos)
            geo_end = pos + length
            lat = 0.0
            lng = 0.0
            gpos = pos
            while gpos < geo_end:
                gfn, gwt, gpos = decode_tag(buf, gpos)
                if gfn == 1 and gwt == 1:
                    lat = struct.unpack_from("<d", buf, gpos)[0]
                    gpos += 8
                elif gfn == 2 and gwt == 1:
                    lng = struct.unpack_from("<d", buf, gpos)[0]
                    gpos += 8
                else:
                    gpos = skip_field(buf, gpos, gwt)
            value = {"latitude": lat, "longitude": lng}
            pos += length
        elif field_number == 9 and wire_type == 2:
            # array
            length, pos = decode_varint(buf, pos)
            value = _decode_array(buf, pos, pos + length)
            pos += length
        elif field_number == 10 and wire_type == 2:
            # timestamp
            length, pos = decode_varint(buf, pos)
            value = _decode_timestamp(buf, pos, pos + length)
            pos += length
        elif field_number == 11 and wire_type == 0:
            # null
            _, pos = decode_varint(buf, pos)
            value = None
        elif field_number == 17 and wire_type == 2:
            # string
            length, pos = decode_varint(buf, pos)
            value = buf[pos : pos + length].decode("utf-8", errors="replace")
            pos += length
        elif field_number == 18 and wire_type == 2:
            # bytes
            length, pos = decode_varint(buf, pos)
            value = buf[pos : pos + length]
            pos += length
        else:
            pos = skip_field(buf, pos, wire_type)

    return value, end


def _decode_document_inner(buf: bytes, pos: int, end: int) -> dict[str, Any]:
    """Decode a Document sub-message into a dict of field_name -> value.

    Document has:
        field 1 = name (string, skip)
        field 2 = repeated MapEntry (the actual fields)
        field 3 = create_time (skip)
        field 4 = update_time (skip)
    """
    fields: dict[str, Any] = {}
    while pos < end:
        field_number, wire_type, pos = decode_tag(buf, pos)
        if field_number == 2 and wire_type == 2:
            # MapEntry
            length, pos = decode_varint(buf, pos)
            entry_end = pos + length
            key, val = _decode_map_entry(buf, pos, entry_end)
            if key is not None:
                fields[key] = val
            pos = entry_end
        else:
            pos = skip_field(buf, pos, wire_type)
    return fields


def decode_document(buf: bytes) -> dict[str, Any] | None:
    """Parse a MaybeDocument protobuf into a Python dict.

    The MaybeDocument wrapper has field 2 = Document.
    Returns None if the document cannot be parsed.
    """
    if not buf:
        return None
    try:
        pos = 0
        end = len(buf)
        while pos < end:
            field_number, wire_type, pos = decode_tag(buf, pos)
            if field_number == 2 and wire_type == 2:
                length, pos = decode_varint(buf, pos)
                return _decode_document_inner(buf, pos, pos + length)
            else:
                pos = skip_field(buf, pos, wire_type)
        return None
    except Exception:
        return None
