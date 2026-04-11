from typing import Any
from palsav.archive import FArchiveReader, FArchiveWriter
from palsav.rawdata import (
    build_process,
    connector,
    map_concrete_model,
    map_concrete_model_module,
    map_model,
)
from loguru import logger
import copy


def decode(
    reader: FArchiveReader, type_name: str, size: int, path: str
) -> dict[str, Any]:
    if type_name != "ArrayProperty":
        raise Exception(f"Expected ArrayProperty, got {type_name}")
    value = reader.property(type_name, size, path, nested_caller_path=path)
    for map_object in value["value"]["values"]:
        map_object["Model"]["value"]["RawData"]["value"] = map_model.decode_bytes(
            reader, map_object["Model"]["value"]["RawData"]["value"]["values"]
        )
        map_object["Model"]["value"]["Connector"]["value"]["RawData"]["value"] = (
            connector.decode_bytes(
                reader,
                map_object["Model"]["value"]["Connector"]["value"]["RawData"]["value"][
                    "values"
                ],
            )
        )
        map_object["Model"]["value"]["BuildProcess"]["value"]["RawData"]["value"] = (
            build_process.decode_bytes(
                reader,
                map_object["Model"]["value"]["BuildProcess"]["value"]["RawData"][
                    "value"
                ]["values"],
            )
        )
        map_object_id = map_object["MapObjectId"]["value"]
        map_object["ConcreteModel"]["value"]["RawData"]["value"] = (
            map_concrete_model.decode_bytes(
                reader,
                map_object["ConcreteModel"]["value"]["RawData"]["value"]["values"],
                map_object_id,
            )
        )
        for module in map_object["ConcreteModel"]["value"]["ModuleMap"]["value"]:
            module_type = module["key"]
            module_bytes = module["value"]["RawData"]["value"]["values"]
            module["value"]["RawData"]["value"] = (
                map_concrete_model_module.decode_bytes(
                    reader, module_bytes, module_type
                )
            )
    return value


def _encode_rawdata_field(
    field_path: str, rawdata: dict[str, Any], encoder_func, *encoder_args
) -> dict[str, Any]:
    """Encode RawData field with defensive copying to prevent reference sharing corruption.

    This function encodes the raw data and returns a NEW dict with 'values' key,
    avoiding in-place modification that could corrupt shared dict references.

    Args:
        field_path: Path identifier for logging (e.g., 'Model', 'ConcreteModel')
        rawdata: The raw data dict to encode
        encoder_func: The encoding function to call
        *encoder_args: Additional arguments for the encoder function

    Returns:
        A new dict with 'values' key containing the encoded bytes
    """
    if "values" in rawdata:
        return rawdata

    try:
        encoded_bytes = encoder_func(rawdata, *encoder_args)
        new_rawdata = {"values": encoded_bytes}
        logger.debug(f"Encoded {field_path}: {len(encoded_bytes)} bytes")
        return new_rawdata
    except Exception as e:
        logger.error(f"Failed to encode {field_path}: {e}")
        raise


def encode(
    writer: FArchiveWriter, property_type: str, properties: dict[str, Any]
) -> int:
    if property_type != "ArrayProperty":
        raise Exception(f"Expected ArrayProperty, got {property_type}")
    del properties["custom_type"]

    known_shared_refs: set[int] = set()

    for map_object in properties["value"]["values"]:
        map_object_id = map_object.get("MapObjectId", {}).get("value", "Unknown")

        rawdata_model = map_object["Model"]["value"]["RawData"]
        if id(rawdata_model) in known_shared_refs:
            logger.debug(
                f"Model RawData at {map_object_id} shares reference with another object"
            )

        if "values" not in rawdata_model["value"]:
            new_value = _encode_rawdata_field(
                f"Model[{map_object_id}]",
                rawdata_model["value"],
                map_model.encode_bytes,
            )
            rawdata_model["value"] = new_value

        rawdata_connector = map_object["Model"]["value"]["Connector"]["value"][
            "RawData"
        ]
        if "values" not in rawdata_connector["value"]:
            new_value = _encode_rawdata_field(
                f"Connector[{map_object_id}]",
                rawdata_connector["value"],
                connector.encode_bytes,
            )
            rawdata_connector["value"] = new_value

        rawdata_buildprocess = map_object["Model"]["value"]["BuildProcess"]["value"][
            "RawData"
        ]
        if "values" not in rawdata_buildprocess["value"]:
            new_value = _encode_rawdata_field(
                f"BuildProcess[{map_object_id}]",
                rawdata_buildprocess["value"],
                build_process.encode_bytes,
            )
            rawdata_buildprocess["value"] = new_value

        rawdata_concrete = map_object["ConcreteModel"]["value"]["RawData"]
        if id(rawdata_concrete["value"]) in known_shared_refs:
            logger.debug(
                f"ConcreteModel RawData at {map_object_id} shares reference with another object - encoding to prevent corruption"
            )

        if "values" not in rawdata_concrete["value"]:
            new_value = _encode_rawdata_field(
                f"ConcreteModel[{map_object_id}]",
                rawdata_concrete["value"],
                map_concrete_model.encode_bytes,
            )
            rawdata_concrete["value"] = new_value

        for module in map_object["ConcreteModel"]["value"]["ModuleMap"]["value"]:
            module_type = module["key"]
            rawdata_module = module["value"]["RawData"]
            if "values" not in rawdata_module["value"]:
                new_value = _encode_rawdata_field(
                    f"Module[{map_object_id}:{module_type}]",
                    rawdata_module["value"],
                    map_concrete_model_module.encode_bytes,
                    module_type,
                )
                rawdata_module["value"] = new_value

    return writer.property_inner(property_type, properties)
