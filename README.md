# palsav-cypy

High-performance Palworld save file parser and converter. Cython-accelerated fork of [palworld-save-tools](https://github.com/oMaN-Rod/palworld-save-tools) with Oodle compression support.

## Install

### With uv

```bash
uv sync
uv run setup.py build_ext --inplace
```

### With pip

```bash
pip install -e .
python setup.py build_ext --inplace
```

> If you skip the Cython build, palsav falls back to pure-Python mode automatically.

## CLI

```bash
# Show help
uv run palsav -h
# pip (after activating venv): palsav -h

# SAV → JSON
uv run palsav Level.sav --to-json
# pip (after activating venv): palsav Level.sav --to-json

# JSON → SAV
uv run palsav Level.sav.json --from-json
# pip (after activating venv): palsav Level.sav.json --from-json

# With options
uv run palsav Level.sav --to-json --minify-json --force
uv run palsav Level.sav.json --from-json --library zlib --output Level_resaved.sav
```

### CLI flags

| Flag | Description |
|------|-------------|
| `--to-json` | Convert SAV to JSON |
| `--from-json` | Convert JSON to SAV |
| `-o, --output` | Output file path |
| `-f, --force` | Overwrite without prompting |
| `--minify-json` | Minify JSON output |
| `--raw` | Output raw GVAS binary |
| `-l, --library` | Compression library: `libooz` (default) or `zlib` |
| `--convert-nan-to-null` | Convert NaN/Inf to null |
| `--custom-properties` | Comma-separated custom properties to decode, or `all` |
| `--debug` | Enable debug logging |
| `--debug-log` | Enable debug logging to file |

## Library

```python
from palsav.palsav import decompress_sav_to_gvas, compress_gvas_to_sav
from palsav.gvas import GvasFile
from palsav.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

# SAV → JSON
with open("Level.sav", "rb") as f:
    raw_gvas, save_type = decompress_sav_to_gvas(f.read())

gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES)
data = gvas_file.dump()

from palsav.json_tools import dump
with open("Level.sav.json", "wb") as f:
    dump(data, f, indent=True)

# JSON → SAV
from palsav.json_tools import load
with open("Level.sav.json", "r") as f:
    data = load(f)

gvas_file = GvasFile.load(data)
sav_bytes = compress_gvas_to_sav(gvas_file.write(PALWORLD_CUSTOM_PROPERTIES), 50)

with open("Level_resaved.sav", "wb") as f:
    f.write(sav_bytes)
```

## Performance

The Cython `FastArchiveReader` uses C-level pointer arithmetic for all primitive reads (int, float, guid, string, etc.) with `nogil` and `noexcept` where possible. Pure Python mode is slow; Cython mode is significantly faster. GC is automatically disabled during parsing and re-enabled after to eliminate collection pauses.

## Dependencies

| Package | Notes |
|---------|-------|
| `loguru` | Logging |
| `orjson` | Fast JSON serialization |
| `pyoozle` | Oodle compression/decompression |
| `cython` | Compiles `_fast_archive.pyx` |
| `setuptools` | Build backend |

## License

MIT
