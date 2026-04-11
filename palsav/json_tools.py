import uuid
from palsav.archive import UUID

try:
    import orjson

    _HAS_ORJSON = True
except ImportError:
    _HAS_ORJSON = False

import json as _stdlib_json


def _default(obj):
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, bytes):
        return obj.hex()
    raise TypeError


def dumps(obj, indent=False, allow_nan=True):
    if _HAS_ORJSON:
        opt = 0
        if indent:
            opt |= orjson.OPT_INDENT_2
        return orjson.dumps(obj, default=_default, option=opt).decode("utf-8")
    cls = _make_encoder()
    return _stdlib_json.dumps(
        obj, indent=2 if indent else None, allow_nan=allow_nan, cls=cls
    )


def dump(obj, f, indent=False, allow_nan=True):
    if _HAS_ORJSON:
        opt = 0
        if indent:
            opt |= orjson.OPT_INDENT_2
        f.write(orjson.dumps(obj, default=_default, option=opt))
    else:
        cls = _make_encoder()
        _stdlib_json.dump(
            obj, f, indent=2 if indent else None, allow_nan=allow_nan, cls=cls
        )


def loads(s):
    if _HAS_ORJSON:
        return orjson.loads(s)
    return _stdlib_json.loads(s)


def load(f):
    return loads(f.read())


def _make_encoder():
    class CustomEncoder(_stdlib_json.JSONEncoder):
        def default(self, obj):
            return _default(obj)

    return CustomEncoder


CustomEncoder = _make_encoder()
