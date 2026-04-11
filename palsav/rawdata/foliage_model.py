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
    data["model_id"] = reader.fstring()
    data["foliage_preset_type"] = reader.byte()
    data["cell_coord"] = {"x": reader.i64(), "y": reader.i64(), "z": reader.i64()}
    data["trailing_bytes"] = reader.byte_list(4)
    if not reader.eof():
        raise Exception("Warning: EOF not reached")
    return data


def _encode_foliage_model_data(properties: dict[str, Any]) -> dict[str, Any]:
    """Encode foliage model data with defensive copying to prevent reference sharing corruption."""
    rawdata = properties["value"]
    if "values" in rawdata:
        return rawdata

    try:
        encoded_bytes = encode_bytes(rawdata)
        new_data = {"values": list(encoded_bytes)}
        logger.debug(f"Encoded foliage model data: {len(encoded_bytes)} bytes")
        return new_data
    except Exception as e:
        logger.error(f"Failed to encode foliage model data: {e}")
        raise


def encode(
    writer: FArchiveWriter, property_type: str, properties: dict[str, Any]
) -> int:
    if property_type != "ArrayProperty":
        raise Exception(f"Expected ArrayProperty, got {property_type}")
    del properties["custom_type"]
    new_value = _encode_foliage_model_data(properties)
    properties["value"] = new_value
    return writer.property_inner(property_type, properties)


def encode_bytes(p: dict[str, Any]) -> bytes:
    writer = FArchiveWriter()
    writer.fstring(p["model_id"])
    writer.byte(p["foliage_preset_type"])
    writer.i64(p["cell_coord"]["x"])
    writer.i64(p["cell_coord"]["y"])
    writer.i64(p["cell_coord"]["z"])
    writer.write(bytes(p["trailing_bytes"]))
    encoded_bytes = writer.bytes()
    return encoded_bytes
