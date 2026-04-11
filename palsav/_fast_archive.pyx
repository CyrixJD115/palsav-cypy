# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: initializedcheck=False

from libc.string cimport memcpy
from libc.stdint cimport int16_t, uint16_t, int32_t, uint32_t, int64_t, uint64_t, uint8_t
from cpython.bytes cimport PyBytes_AS_STRING, PyBytes_GET_SIZE, PyBytes_FromStringAndSize
from cpython.unicode cimport PyUnicode_DecodeASCII
from cpython.dict cimport PyDict_New
from cpython.list cimport PyList_New, PyList_SET_ITEM
from cpython.ref cimport Py_INCREF

import struct
import math
import uuid as _stdlib_uuid
from typing import Any, Callable, Optional, Sequence, Union
from loguru import logger

from palsav.archive import UUID as _UUID

_float = float
_bytes = bytes


cdef class FastArchiveReader:
    cdef:
        const unsigned char* _buf
        Py_ssize_t _pos
        Py_ssize_t _size
        object _data_owner
        dict _type_hints
        dict _custom_properties
        bint _debug
        bint _allow_nan

    @property
    def size(self):
        return self._size

    @property
    def type_hints(self):
        return self._type_hints

    @property
    def custom_properties(self):
        return self._custom_properties

    @property
    def debug(self):
        return self._debug

    @property
    def allow_nan(self):
        return self._allow_nan

    def __init__(self, data, dict type_hints=None, dict custom_properties=None,
                 bint debug=False, bint allow_nan=True):
        if type_hints is None:
            type_hints = {}
        if custom_properties is None:
            custom_properties = {}
        if isinstance(data, bytes):
            self._data_owner = data
        elif isinstance(data, memoryview):
            self._data_owner = bytes(data)
        else:
            self._data_owner = bytes(data)
        self._buf = <const unsigned char*>PyBytes_AS_STRING(self._data_owner)
        self._pos = 0
        self._size = PyBytes_GET_SIZE(self._data_owner)
        self._type_hints = type_hints
        self._custom_properties = custom_properties
        self._debug = debug
        self._allow_nan = allow_nan

    def __enter__(self):
        self._pos = 0
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def internal_copy(self, data, bint debug=False):
        return FastArchiveReader(
            data, self._type_hints, self._custom_properties,
            debug=debug, allow_nan=self._allow_nan
        )

    cpdef Py_ssize_t tell(self):
        return self._pos

    cpdef seek(self, Py_ssize_t pos):
        self._pos = pos

    # ── C-level primitive reads (inlined, no GIL) ──────────────────────

    cdef inline int16_t _ci16(self) noexcept nogil:
        cdef const unsigned char* p = self._buf + self._pos
        self._pos += 2
        return <int16_t>(p[0] | (<uint16_t>p[1] << 8))

    cdef inline uint16_t _cu16(self) noexcept nogil:
        cdef const unsigned char* p = self._buf + self._pos
        self._pos += 2
        return p[0] | (<uint16_t>p[1] << 8)

    cdef inline int32_t _ci32(self) noexcept nogil:
        cdef const unsigned char* p = self._buf + self._pos
        self._pos += 4
        return <int32_t>(p[0] | (<uint32_t>p[1] << 8) | (<uint32_t>p[2] << 16) | (<uint32_t>p[3] << 24))

    cdef inline uint32_t _cu32(self) noexcept nogil:
        cdef const unsigned char* p = self._buf + self._pos
        self._pos += 4
        return p[0] | (<uint32_t>p[1] << 8) | (<uint32_t>p[2] << 16) | (<uint32_t>p[3] << 24)

    cdef inline int64_t _ci64(self) noexcept nogil:
        cdef const unsigned char* p = self._buf + self._pos
        self._pos += 8
        return <int64_t>((<uint64_t>p[0]) | (<uint64_t>p[1] << 8) | (<uint64_t>p[2] << 16) | (<uint64_t>p[3] << 24) | (<uint64_t>p[4] << 32) | (<uint64_t>p[5] << 40) | (<uint64_t>p[6] << 48) | (<uint64_t>p[7] << 56))

    cdef inline uint64_t _cu64(self) noexcept nogil:
        cdef const unsigned char* p = self._buf + self._pos
        self._pos += 8
        return (p[0] | (<uint64_t>p[1] << 8) | (<uint64_t>p[2] << 16) | (<uint64_t>p[3] << 24) | (<uint64_t>p[4] << 32) | (<uint64_t>p[5] << 40) | (<uint64_t>p[6] << 48) | (<uint64_t>p[7] << 56))

    cdef inline float _cfloat(self) noexcept nogil:
        cdef float val
        memcpy(&val, self._buf + self._pos, 4)
        self._pos += 4
        return val

    cdef inline double _cdouble(self) noexcept nogil:
        cdef double val
        memcpy(&val, self._buf + self._pos, 8)
        self._pos += 8
        return val

    cdef inline uint8_t _cbyte(self) noexcept nogil:
        cdef uint8_t val = self._buf[self._pos]
        self._pos += 1
        return val

    # ── C-dispatch internal methods ────────────────────────────────────

    cdef str _cfstring(self):
        cdef int32_t raw_size = self._ci32()
        if raw_size == 0:
            return ""
        cdef Py_ssize_t p = self._pos
        cdef Py_ssize_t byte_len
        cdef const unsigned char* src = self._buf + p
        cdef bytes chunk
        cdef str result
        cdef int32_t size

        if raw_size < 0:
            size = -raw_size
            if p + size * 2 > self._size:
                raise Exception(f"fstring read past end of buffer (pos={p}, size={size}, bufsize={self._size})")
            byte_len = size * 2 - 2
            self._pos = p + size * 2
            chunk = PyBytes_FromStringAndSize(<char*>src, byte_len)
            try:
                result = chunk.decode("utf-16-le")
            except Exception:
                result = chunk.decode("utf-16-le", errors="surrogatepass")
        else:
            if p + raw_size > self._size:
                raise Exception(f"fstring read past end of buffer (pos={p}, size={raw_size}, bufsize={self._size})")
            byte_len = raw_size - 1
            self._pos = p + raw_size
            try:
                result = PyUnicode_DecodeASCII(<char*>src, byte_len, NULL)
            except Exception:
                result = PyUnicode_DecodeASCII(<char*>src, byte_len, "surrogatepass")
        return result

    cdef object _cguid(self):
        cdef Py_ssize_t p = self._pos
        self._pos = p + 16
        return _UUID(PyBytes_FromStringAndSize(<char*>(self._buf + p), 16))

    cdef object _coptional_guid(self):
        cdef Py_ssize_t p = self._pos
        if self._buf[p]:
            self._pos = p + 1
            return self._cguid()
        self._pos = p + 1
        return None

    cdef object _get_type_or(self, str path, str default):
        cdef dict th = self._type_hints
        if path in th:
            return th[path]
        if self._debug:
            logger.debug(f"Struct type for {path} not found, assuming {default}")
        return default

    # ── Python-visible API ─────────────────────────────────────────────

    cpdef bint eof(self):
        return self._pos >= self._size

    cpdef bytes read(self, Py_ssize_t size):
        cdef Py_ssize_t p = self._pos
        cdef bytes result = PyBytes_FromStringAndSize(<char*>(self._buf + p), size)
        self._pos = p + size
        return result

    cpdef bytes read_to_end(self):
        cdef Py_ssize_t remaining = self._size - self._pos
        cdef bytes result = PyBytes_FromStringAndSize(<char*>(self._buf + self._pos), remaining)
        self._pos = self._size
        return result

    def i16(self):
        return int(self._ci16())

    def u16(self):
        return int(self._cu16())

    def i32(self):
        return int(self._ci32())

    def u32(self):
        return int(self._cu32())

    def i64(self):
        return int(self._ci64())

    def u64(self):
        return int(self._cu64())

    def float(self):
        cdef double val = self._cfloat()
        if self._allow_nan:
            return val
        if val != val:
            return None
        return val

    def double(self):
        cdef double val = self._cdouble()
        if self._allow_nan:
            return val
        if val != val:
            return None
        return val

    def byte(self):
        return int(self._cbyte())

    def bool(self):
        return self._cbyte() > 0

    cpdef fstring(self):
        return self._cfstring()

    cpdef guid(self):
        return self._cguid()

    cpdef optional_guid(self):
        return self._coptional_guid()

    def byte_list(self, Py_ssize_t size):
        cdef Py_ssize_t p = self._pos
        cdef bytes result = PyBytes_FromStringAndSize(<char*>(self._buf + p), size)
        self._pos = p + size
        return result

    def skip(self, Py_ssize_t size):
        self._pos += size

    def get_type_or(self, str path, str default):
        return self._get_type_or(path, default)

    # ── Core parsing loop ──────────────────────────────────────────────

    cpdef dict properties_until_end(self, str path=""):
        cdef dict properties = {}
        cdef dict custom_props = self._custom_properties
        cdef str name
        cdef str type_name
        cdef uint64_t size
        cdef str prop_path

        while True:
            if self._pos >= self._size:
                raise Exception(f"Unexpected end of data in properties_until_end (path={path})")
            name = self._cfstring()
            if name == "None":
                break
            type_name = self._cfstring()
            size = self._cu64()
            prop_path = f"{path}.{name}"
            properties[name] = self._property_impl(type_name, size, prop_path, "")
        return properties

    def property(self, str type_name, uint64_t size, str path, str nested_caller_path=""):
        return self._property_impl(type_name, size, path, nested_caller_path)

    cdef dict _property_impl(self, str type_name, uint64_t size, str path, str nested_caller_path):
        cdef dict value
        cdef dict custom_props = self._custom_properties

        if path in custom_props and (path is not nested_caller_path or nested_caller_path == ""):
            value = <dict>custom_props[path][0](self, type_name, size, path)
            value["custom_type"] = path
        elif type_name == "StructProperty":
            value = self._struct(path)
        elif type_name == "IntProperty":
            value = {"id": self._coptional_guid(), "value": self._ci32()}
        elif type_name == "UInt16Property":
            value = {"id": self._coptional_guid(), "value": self._cu16()}
        elif type_name == "UInt32Property":
            value = {"id": self._coptional_guid(), "value": self._cu32()}
        elif type_name == "UInt64Property":
            value = {"id": self._coptional_guid(), "value": self._cu64()}
        elif type_name == "Int64Property":
            value = {"id": self._coptional_guid(), "value": self._ci64()}
        elif type_name == "FixedPoint64Property":
            value = {"id": self._coptional_guid(), "value": self._ci32()}
        elif type_name == "FloatProperty":
            value = {"id": self._coptional_guid(), "value": self._read_float_val()}
        elif type_name == "StrProperty":
            value = {"id": self._coptional_guid(), "value": self._cfstring()}
        elif type_name == "NameProperty":
            value = {"id": self._coptional_guid(), "value": self._cfstring()}
        elif type_name == "EnumProperty":
            value = self._read_enum_property()
        elif type_name == "BoolProperty":
            value = {"value": self._cbyte() > 0, "id": self._coptional_guid()}
        elif type_name == "ByteProperty":
            value = self._read_byte_property()
        elif type_name == "ArrayProperty":
            value = self._read_array_property(path, size)
        elif type_name == "MapProperty":
            value = self._read_map_property(path)
        elif type_name == "SetProperty":
            value = self._read_set_property()
        else:
            raise Exception(f"Unknown type: {type_name} ({path})")

        value["type"] = type_name
        return value

    cdef double _read_float_val(self):
        cdef double val = self._cfloat()
        if self._allow_nan:
            return val
        if val != val:
            return float('nan')
        return val

    cdef dict _read_enum_property(self):
        cdef str enum_type = self._cfstring()
        cdef object _id = self._coptional_guid()
        cdef str enum_value = self._cfstring()
        return {"id": _id, "value": {"type": enum_type, "value": enum_value}}

    cdef dict _read_byte_property(self):
        cdef str enum_type = self._cfstring()
        cdef object _id = self._coptional_guid()
        if enum_type == "None":
            return {"id": _id, "value": {"type": enum_type, "value": self._cbyte()}}
        else:
            return {"id": _id, "value": {"type": enum_type, "value": self._cfstring()}}

    cdef dict _read_array_property(self, str path, uint64_t size):
        cdef str array_type = self._cfstring()
        cdef object _id = self._coptional_guid()
        return {"array_type": array_type, "id": _id, "value": self._array_property_impl(array_type, size - 4, path)}

    cdef dict _read_map_property(self, str path):
        cdef str key_type = self._cfstring()
        cdef str value_type = self._cfstring()
        cdef object _id = self._coptional_guid()
        self._cu32()
        cdef uint32_t count = self._cu32()
        cdef str key_path = path + ".Key"
        cdef str value_path = path + ".Value"
        cdef str key_struct_type = None
        cdef str value_struct_type = None

        if key_type == "StructProperty":
            key_struct_type = <str>self._get_type_or(key_path, "Guid")
        if value_type == "StructProperty":
            value_struct_type = <str>self._get_type_or(value_path, "StructProperty")

        cdef list values = []
        for _ in range(count):
            values.append({
                "key": self._prop_value(key_type, key_struct_type, key_path),
                "value": self._prop_value(value_type, value_struct_type, value_path),
            })

        return {
            "key_type": key_type, "value_type": value_type,
            "key_struct_type": key_struct_type, "value_struct_type": value_struct_type,
            "id": _id, "value": values,
        }

    cdef dict _read_set_property(self):
        cdef str set_type = self._cfstring()
        cdef object _id = self._coptional_guid()
        self._cu32()
        cdef uint32_t count = self._cu32()
        return {"set_type": set_type, "id": _id, "value": [self.properties_until_end() for _ in range(count)]}

    # ── Struct / prop_value / array ────────────────────────────────────

    cdef dict _struct(self, str path):
        cdef str struct_type = self._cfstring()
        cdef object struct_id = self._cguid()
        cdef object _id = self._coptional_guid()
        cdef object value = self._struct_value(struct_type, path)
        return {"struct_type": struct_type, "struct_id": struct_id, "id": _id, "value": value}

    def struct(self, str path):
        return self._struct(path)

    cdef object _struct_value(self, str struct_type, str path=""):
        if struct_type == "Vector":
            return {"x": self._cdouble(), "y": self._cdouble(), "z": self._cdouble()}
        elif struct_type == "DateTime":
            return self._cu64()
        elif struct_type == "Guid":
            return self._cguid()
        elif struct_type == "Quat":
            return {"x": self._cdouble(), "y": self._cdouble(), "z": self._cdouble(), "w": self._cdouble()}
        elif struct_type == "LinearColor":
            return {"r": self._cfloat(), "g": self._cfloat(), "b": self._cfloat(), "a": self._cfloat()}
        elif struct_type == "Color":
            return {"b": self._cbyte(), "g": self._cbyte(), "r": self._cbyte(), "a": self._cbyte()}
        else:
            if self._debug:
                logger.debug(f"Assuming struct type: {struct_type} ({path})")
            return self.properties_until_end(path)

    def struct_value(self, str struct_type, str path=""):
        return self._struct_value(struct_type, path)

    cdef object _prop_value(self, str type_name, str struct_type_name, str path):
        if type_name == "StructProperty":
            return self._struct_value(struct_type_name, path)
        elif type_name == "EnumProperty":
            return self._cfstring()
        elif type_name == "NameProperty":
            return self._cfstring()
        elif type_name == "IntProperty":
            return self._ci32()
        elif type_name == "BoolProperty":
            return self._cbyte() > 0
        elif type_name == "UInt32Property":
            return self._cu32()
        elif type_name == "StrProperty":
            return self._cfstring()
        else:
            raise Exception(f"Unknown property value type: {type_name} ({path})")

    def prop_value(self, str type_name, str struct_type_name, str path):
        return self._prop_value(type_name, struct_type_name, path)

    cdef object _array_property_impl(self, str array_type, uint64_t size, str path):
        cdef uint32_t count = self._cu32()
        cdef str prop_name
        cdef str prop_type
        cdef str type_name
        cdef str sub_path
        cdef list prop_values
        cdef object _id

        if array_type == "StructProperty":
            prop_name = self._cfstring()
            prop_type = self._cfstring()
            self._cu64()
            type_name = self._cfstring()
            _id = self._cguid()
            self._pos += 1  # skip(1)
            prop_values = []
            sub_path = f"{path}.{prop_name}"
            for _ in range(count):
                prop_values.append(self._struct_value(type_name, sub_path))
            return {"prop_name": prop_name, "prop_type": prop_type, "values": prop_values, "type_name": type_name, "id": _id}
        else:
            return {"values": self._array_value_impl(array_type, count, size, path)}

    def array_property(self, str array_type, uint64_t size, str path):
        return self._array_property_impl(array_type, size, path)

    cdef list _array_value_impl(self, str array_type, uint64_t count, uint64_t size, str path):
        cdef list values = []
        if array_type == "EnumProperty":
            for _ in range(count):
                values.append(self._cfstring())
        elif array_type == "NameProperty":
            for _ in range(count):
                values.append(self._cfstring())
        elif array_type == "Guid":
            for _ in range(count):
                values.append(self._cguid())
        elif array_type == "ByteProperty":
            if size == count:
                return list(self.byte_list(count))
            else:
                raise Exception("Labelled ByteProperty not implemented")
        else:
            raise Exception(f"Unknown array type: {array_type} ({path})")
        return values

    def array_value(self, str array_type, uint64_t count, uint64_t size, str path):
        return self._array_value_impl(array_type, count, size, path)

    def tarray(self, type_reader):
        cdef uint32_t count = self._cu32()
        return [type_reader(self) for _ in range(count)]

    # ── Geometry / transform helpers ───────────────────────────────────

    def compressed_short_rotator(self):
        cdef uint16_t short_pitch = 0
        cdef uint16_t short_yaw = 0
        cdef uint16_t short_roll = 0
        if self._cbyte() > 0:
            short_pitch = self._cu16()
        if self._cbyte() > 0:
            short_yaw = self._cu16()
        if self._cbyte() > 0:
            short_roll = self._cu16()
        return (short_pitch * (360.0 / 65536.0), short_yaw * (360.0 / 65536.0), short_roll * (360.0 / 65536.0))

    def serializeint(self, int component_bit_count):
        cdef Py_ssize_t nbytes = (component_bit_count + 7) // 8
        cdef Py_ssize_t p = self._pos
        self._pos = p + nbytes
        cdef const unsigned char* src = self._buf + p
        cdef uint64_t val = 0
        cdef Py_ssize_t i
        for i in range(nbytes):
            val |= <uint64_t>src[i] << (8 * i)
        if component_bit_count % 8 != 0:
            val &= (<uint64_t>1 << component_bit_count) - 1
        if val & (<uint64_t>1 << (component_bit_count - 1)):
            val -= <uint64_t>1 << component_bit_count
        return int(<int64_t>val)

    def packed_vector(self, int scale_factor):
        cdef uint32_t raw = self._cu32()
        cdef uint32_t component_bit_count = raw & 63
        cdef uint32_t extra_info = raw >> 6
        cdef int sign_bit, x, y, z

        if component_bit_count > 0:
            x = self.serializeint(component_bit_count)
            y = self.serializeint(component_bit_count)
            z = self.serializeint(component_bit_count)
            sign_bit = 1 << component_bit_count - 1
            x = (x & sign_bit - 1) - (x & sign_bit)
            y = (y & sign_bit - 1) - (y & sign_bit)
            z = (z & sign_bit - 1) - (z & sign_bit)
            if extra_info:
                return (x / scale_factor, y / scale_factor, z / scale_factor)
            return (x, y, z)
        else:
            if extra_info:
                return self.vector()
            else:
                return (self._cfloat(), self._cfloat(), self._cfloat())

    def vector(self):
        return (self._cdouble(), self._cdouble(), self._cdouble())

    def vector_dict(self):
        return {"x": self._cdouble(), "y": self._cdouble(), "z": self._cdouble()}

    def quat(self):
        return (self._cdouble(), self._cdouble(), self._cdouble(), self._cdouble())

    def quat_dict(self):
        return {"x": self._cdouble(), "y": self._cdouble(), "z": self._cdouble(), "w": self._cdouble()}

    def ftransform(self):
        return {"rotation": self.quat_dict(), "translation": self.vector_dict(), "scale3d": self.vector_dict()}
