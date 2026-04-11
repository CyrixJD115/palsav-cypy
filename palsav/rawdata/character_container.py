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
    parent_reader: FArchiveReader, c_bytes: Sequence[int]
) -> Optional[dict[str, Any]]:
    if len(c_bytes) == 0:
        return None
    reader = parent_reader.internal_copy(c_bytes, debug=False)
    data = {
        "player_uid": reader.guid(),
        "instance_id": reader.guid(),
        "permission_tribe_id": reader.byte(),
    }
    if not reader.eof():
        unknown_bytes = [int(b) for b in reader.read_to_end()]
        logger.debug(
            f"Unknown data in character container: {' '.join((f'{b:02x}' for b in unknown_bytes))}"
        )
        data["unknown_bytes"] = unknown_bytes
    return data


def _encode_character_container_data(properties: dict[str, Any]) -> dict[str, Any]:
    """Encode character container data with defensive copying to prevent reference sharing corruption."""
    rawdata = properties["value"]
    if rawdata is None:
        return {"values": []}
    if "values" in rawdata:
        return rawdata

    try:
        encoded_bytes = encode_bytes(rawdata)
        new_data = {"values": list(encoded_bytes)}
        logger.debug(f"Encoded character container data: {len(encoded_bytes)} bytes")
        return new_data
    except Exception as e:
        logger.error(f"Failed to encode character container data: {e}")
        raise


def encode(
    writer: FArchiveWriter, property_type: str, properties: dict[str, Any]
) -> int:
    if property_type != "ArrayProperty":
        raise Exception(f"Expected ArrayProperty, got {property_type}")
    del properties["custom_type"]
    new_value = _encode_character_container_data(properties)
    properties["value"] = new_value
    return writer.property_inner(property_type, properties)


def encode_bytes(p: dict[str, Any]) -> bytes:
    if p is None:
        return bytes()
    writer = FArchiveWriter()
    writer.guid(p["player_uid"])
    writer.guid(p["instance_id"])
    writer.byte(p["permission_tribe_id"])
    if "unknown_bytes" in p:
        writer.write(bytes(p["unknown_bytes"]))
    encoded_bytes = writer.bytes()
    return encoded_bytes
