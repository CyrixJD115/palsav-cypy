import sys
from palsav.compressor import Compressor
from palsav.compressor.oozlib import OozLib
from palsav.compressor.zlib import Zlib
from palsav.compressor.enums import SaveType
from loguru import logger

compressor = Compressor()
z_lib = Zlib()
oozlib = OozLib()


def configure_logging(debug: bool = False):
    if debug:
        logger.remove()
        logger.add(
            sys.stdout,
            colorize=True,
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | <level>{level: <8}</level> | <cyan>{name}</cyan>:<blue>{function}</blue>:{line} 🡆 {message}",
        )
    else:
        logger.remove()
        logger.add(
            sys.stdout, format="<level>{level}</level> 🡆 {message}", level="INFO"
        )


def decompress_sav_to_gvas(data: bytes, debug: bool = False) -> tuple[bytes, int]:
    configure_logging(debug)
    format = compressor.check_sav_format(data)
    if format is None:
        raise Exception("Unknown save format")
    match format:
        case SaveType.PLZ | SaveType.CNK:
            return z_lib.decompress(data)
        case SaveType.PLM:
            return oozlib.decompress(data)
        case _:
            raise Exception("Unknown save format")


def compress_gvas_to_sav(data: bytes, save_type: int, debug: bool = False) -> bytes:
    configure_logging(debug)
    format = compressor.check_savtype_format(save_type)
    if format is None:
        raise Exception("Unknown save type format")
    match format:
        case SaveType.PLZ | SaveType.CNK:
            return z_lib.compress(data, save_type)
        case SaveType.PLM:
            return oozlib.compress(data, save_type)
