from typing import Any, Optional, Sequence
from loguru import logger
from palsav.archive import FArchiveReader, FArchiveWriter
from palsav.rawdata.common import (
    lab_research_rep_info_read,
    lab_research_rep_info_writer,
)


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
    parent_reader: FArchiveReader, m_bytes: Sequence[int]
) -> dict[str, Any]:
    reader = parent_reader.internal_copy(m_bytes, debug=False)
    data: dict[str, Any] = {}
    data["research_info"] = reader.tarray(lab_research_rep_info_read)
    data["current_research_id"] = reader.fstring()
    if not reader.eof():
        data["trailing_bytes"] = [int(b) for b in reader.read_to_end()]
    return data


def _encode_guild_lab_data(properties: dict[str, Any]) -> dict[str, Any]:
    """Encode guild lab data with defensive copying to prevent reference sharing corruption."""
    rawdata = properties["value"]
    if rawdata is None:
        return {"values": []}
    if "values" in rawdata:
        return rawdata

    try:
        encoded_bytes = encode_bytes(rawdata)
        new_data = {"values": list(encoded_bytes)}
        logger.debug(f"Encoded guild lab data: {len(encoded_bytes)} bytes")
        return new_data
    except Exception as e:
        logger.error(f"Failed to encode guild lab data: {e}")
        raise


def encode(
    writer: FArchiveWriter, property_type: str, properties: dict[str, Any]
) -> int:
    if property_type != "ArrayProperty":
        raise Exception(f"Expected ArrayProperty, got {property_type}")
    del properties["custom_type"]
    new_value = _encode_guild_lab_data(properties)
    properties["value"] = new_value
    return writer.property_inner(property_type, properties)


def encode_bytes(p: Optional[dict[str, Any]]) -> bytes:
    if p is None:
        return b""
    writer = FArchiveWriter()
    writer.tarray(lab_research_rep_info_writer, p["research_info"])
    writer.fstring(p["current_research_id"])
    if "trailing_bytes" in p:
        writer.write(bytes(p["trailing_bytes"]))
    encoded_bytes = writer.bytes()
    return encoded_bytes
