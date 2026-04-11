import os
import sys
from setuptools import setup, Extension

try:
    from Cython.Build import cythonize

    USE_CYTHON = True
except ImportError:
    USE_CYTHON = False
    print("Cython not found. Skipping Cython extension compilation.")
    print("Install with: pip install cython")
    cythonize = None

if USE_CYTHON:
    ext_modules = cythonize(
        Extension(
            "palsav._fast_archive",
            ["palsav/_fast_archive.pyx"],
            define_macros=[("PY_SSIZE_T_CLEAN", "1")],
        ),
        compiler_directives={
            "language_level": "3",
            "boundscheck": False,
            "wraparound": False,
            "cdivision": True,
            "initializedcheck": False,
        },
        annotate=False,
    )
else:
    ext_modules = []

setup(
    name="palsav-ext",
    version="0.1.0",
    ext_modules=ext_modules,
    packages=[],
    py_modules=[],
)
