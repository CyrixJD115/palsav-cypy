from typing import Any, Sequence
from loguru import logger
from palsav.archive import *


def decode(
    reader: FArchiveReader, type_name: str, size: int, path: str
) -> dict[str, Any]:
    if type_name != "ArrayProperty":
        raise Exception(f"Expected ArrayProperty, got {type_name}")
    value = reader.property(type_name, size, path, nested_caller_path=path)
    char_bytes = value["value"]["values"]
    value["value"] = decode_bytes(reader, char_bytes)
    return value


def decode_bytes(
    parent_reader: FArchiveReader, char_bytes: Sequence[int]
) -> dict[str, Any]:
    reader = parent_reader.internal_copy(char_bytes, debug=False)
    char_data = {
        "object": reader.properties_until_end(),
        "unknown_bytes": reader.byte_list(4),
        "group_id": reader.guid(),
    }
    char_data["trailing_bytes"] = reader.byte_list(4)
    if not reader.eof():
        raise Exception("Warning: EOF not reached")
    return char_data


def _encode_character_data(properties: dict[str, Any]) -> dict[str, Any]:
    """Encode character data with defensive copying to prevent reference sharing corruption.

    Returns a NEW dict with 'values' key to avoid modifying potentially shared references.
    """
    rawdata = properties["value"]
    if "values" in rawdata:
        return rawdata

    try:
        encoded_bytes = encode_bytes(rawdata)
        new_data = {"values": list(encoded_bytes)}
        logger.debug(f"Encoded character data: {len(encoded_bytes)} bytes")
        return new_data
    except Exception as e:
        logger.error(f"Failed to encode character data: {e}")
        raise


def encode(
    writer: FArchiveWriter, property_type: str, properties: dict[str, Any]
) -> int:
    if property_type != "ArrayProperty":
        raise Exception(f"Expected ArrayProperty, got {property_type}")
    del properties["custom_type"]
    new_value = _encode_character_data(properties)
    properties["value"] = new_value
    return writer.property_inner(property_type, properties)


def encode_bytes(p: dict[str, Any]) -> bytes:
    writer = FArchiveWriter()
    writer.properties(p["object"])
    writer.write(bytes(p["unknown_bytes"]))
    writer.guid(p["group_id"])
    writer.write(bytes(p["trailing_bytes"]))
    encoded_bytes = writer.bytes()
    return encoded_bytes
