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
    data = {}
    data["permission"] = {
        "type_a": reader.tarray(lambda r: r.byte()),
        "type_b": reader.tarray(lambda r: r.byte()),
        "item_static_ids": reader.tarray(lambda r: r.fstring()),
    }
    if not reader.eof():
        data["trailing_unparsed_data"] = [b for b in reader.read_to_end()]
    return data


def _encode_item_container_data(properties: dict[str, Any]) -> dict[str, Any]:
    """Encode item container data with defensive copying to prevent reference sharing corruption.

    Returns a NEW dict with 'values' key to avoid modifying potentially shared references.
    """
    rawdata = properties["value"]
    if rawdata is None:
        return {"values": []}
    if "values" in rawdata:
        return rawdata

    try:
        encoded_bytes = encode_bytes(rawdata)
        new_data = {"values": list(encoded_bytes)}
        logger.debug(f"Encoded item container data: {len(encoded_bytes)} bytes")
        return new_data
    except Exception as e:
        logger.error(f"Failed to encode item container data: {e}")
        raise


def encode(
    writer: FArchiveWriter, property_type: str, properties: dict[str, Any]
) -> int:
    if property_type != "ArrayProperty":
        raise Exception(f"Expected ArrayProperty, got {property_type}")
    del properties["custom_type"]
    new_value = _encode_item_container_data(properties)
    properties["value"] = new_value
    return writer.property_inner(property_type, properties)


def encode_bytes(p: dict[str, Any]) -> bytes:
    if p is None:
        return bytes()
    writer = FArchiveWriter()
    writer.tarray(lambda w, d: w.byte(d), p["permission"]["type_a"])
    writer.tarray(lambda w, d: w.byte(d), p["permission"]["type_b"])
    writer.tarray(
        lambda w, d: (w.fstring(d), None)[1], p["permission"]["item_static_ids"]
    )
    if "trailing_unparsed_data" in p:
        writer.write(bytes(p["trailing_unparsed_data"]))
    encoded_bytes = writer.bytes()
    return encoded_bytes
