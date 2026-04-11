from typing import Any, Sequence, Optional
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
    parent_reader: FArchiveReader, c_bytes: Sequence[int]
) -> Optional[dict[str, Any]]:
    if len(c_bytes) == 0:
        return None
    reader = parent_reader.internal_copy(c_bytes, debug=False)
    data = {
        "slot_index": reader.i32(),
        "count": reader.i32(),
        "item": {
            "static_id": reader.fstring(),
            "dynamic_id": {
                "created_world_id": reader.guid(),
                "local_id_in_created_world": reader.guid(),
            },
        },
        "trailing_bytes": [int(b) for b in reader.read_to_end()],
    }
    return data


def _encode_item_container_slots_data(properties: dict[str, Any]) -> dict[str, Any]:
    """Encode item container slots data with defensive copying to prevent reference sharing corruption."""
    rawdata = properties["value"]
    if rawdata is None:
        return {"values": []}
    if "values" in rawdata:
        return rawdata

    try:
        encoded_bytes = encode_bytes(rawdata)
        new_data = {"values": list(encoded_bytes)}
        logger.debug(f"Encoded item container slots data: {len(encoded_bytes)} bytes")
        return new_data
    except Exception as e:
        logger.error(f"Failed to encode item container slots data: {e}")
        raise


def encode(
    writer: FArchiveWriter, property_type: str, properties: dict[str, Any]
) -> int:
    if property_type != "ArrayProperty":
        raise Exception(f"Expected ArrayProperty, got {property_type}")
    del properties["custom_type"]
    new_value = _encode_item_container_slots_data(properties)
    properties["value"] = new_value
    return writer.property_inner(property_type, properties)


def encode_bytes(p: dict[str, Any]) -> bytes:
    if p is None:
        return bytes()
    writer = FArchiveWriter()
    writer.i32(p["slot_index"])
    writer.i32(p["count"])
    writer.fstring(p["item"]["static_id"])
    writer.guid(p["item"]["dynamic_id"]["created_world_id"])
    writer.guid(p["item"]["dynamic_id"]["local_id_in_created_world"])
    writer.write(bytes(p["trailing_bytes"]))
    encoded_bytes = writer.bytes()
    return encoded_bytes
