from typing import Any, Sequence
from loguru import logger
from palsav.archive import *


def decode(
    reader: FArchiveReader, type_name: str, size: int, path: str
) -> dict[str, Any]:
    if type_name != "ArrayProperty":
        raise Exception(f"Expected ArrayProperty, got {type_name}")
    value = reader.property(type_name, size, path, nested_caller_path=path)
    data_bytes = value["value"]["values"]
    value["value"] = decode_bytes(reader, data_bytes)
    return value


def decode_bytes(
    parent_reader: FArchiveReader, b_bytes: Sequence[int]
) -> dict[str, Any]:
    reader = parent_reader.internal_copy(b_bytes, debug=False)
    data: dict[str, Any] = {}
    data["id"] = reader.guid()
    data["spawn_transform"] = reader.ftransform()
    data["current_order_type"] = reader.byte()
    data["current_battle_type"] = reader.byte()
    data["container_id"] = reader.guid()
    data["trailing_bytes"] = reader.byte_list(4)
    if not reader.eof():
        raise Exception("Warning: EOF not reached")
    return data


def _encode_worker_director_data(properties: dict[str, Any]) -> dict[str, Any]:
    """Encode worker director data with defensive copying to prevent reference sharing corruption."""
    rawdata = properties["value"]
    if "values" in rawdata:
        return rawdata

    try:
        encoded_bytes = encode_bytes(rawdata)
        new_data = {"values": list(encoded_bytes)}
        logger.debug(f"Encoded worker director data: {len(encoded_bytes)} bytes")
        return new_data
    except Exception as e:
        logger.error(f"Failed to encode worker director data: {e}")
        raise


def encode(
    writer: FArchiveWriter, property_type: str, properties: dict[str, Any]
) -> int:
    if property_type != "ArrayProperty":
        raise Exception(f"Expected ArrayProperty, got {property_type}")
    del properties["custom_type"]
    new_value = _encode_worker_director_data(properties)
    properties["value"] = new_value
    return writer.property_inner(property_type, properties)


def encode_bytes(p: dict[str, Any]) -> bytes:
    writer = FArchiveWriter()
    writer.guid(p["id"])
    writer.ftransform(p["spawn_transform"])
    writer.byte(p["current_order_type"])
    writer.byte(p["current_battle_type"])
    writer.guid(p["container_id"])
    writer.write(bytes(p["trailing_bytes"]))
    encoded_bytes = writer.bytes()
    return encoded_bytes
