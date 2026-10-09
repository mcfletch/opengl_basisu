"""Build the transcoder extension.

The extension is the package: there is no pure-Python transcoder to fall back
to, so a failed build is a failed install. It compiles three things:

* ``src/opengl_basisu/_transcoder.pyx``, the Cython binding, as C++;
* ``vendor/basis_universal/transcoder/basisu_transcoder.cpp``, the transcoder;
* ``vendor/basis_universal/zstd/zstddeclib.c``, the Zstandard decoder that
  UASTC KTX 2 files are supercompressed with, compiled as C and linked into
  the extension.

The transcoder is compiled with ``-fno-strict-aliasing`` because its header
says it must be, and as C++17, the standard its own build uses.
"""

import sys

from Cython.Build import cythonize
from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext as _build_ext

VENDOR = 'vendor/basis_universal'
DEFINES = [
    ('BASISD_SUPPORT_KTX2', '1'),
    ('BASISD_SUPPORT_KTX2_ZSTD', '1'),
]

if sys.platform == 'win32':
    CXX_FLAGS = ['/std:c++17', '/EHsc', '/bigobj']
    C_FLAGS: list[str] = []
else:
    # -g0 overrides the -g in Python's own CFLAGS: the transcoder's debug
    # information is most of the size of a wheel.
    CXX_FLAGS = ['-std=c++17', '-fno-strict-aliasing', '-fvisibility=hidden', '-O2', '-g0']
    C_FLAGS = ['-fno-strict-aliasing', '-fvisibility=hidden', '-O2', '-g0', '-fPIC']


extensions = cythonize(
    [
        Extension(
            'opengl_basisu._transcoder',
            sources=[
                'src/opengl_basisu/_transcoder.pyx',
                VENDOR + '/transcoder/basisu_transcoder.cpp',
            ],
            include_dirs=['src/opengl_basisu', VENDOR + '/transcoder'],
            define_macros=DEFINES,
            extra_compile_args=CXX_FLAGS,
            language='c++',
        )
    ],
    compiler_directives={'language_level': '3'},
)

C_SOURCES = [VENDOR + '/zstd/zstddeclib.c']


class build_ext(_build_ext):
    """Compile the C sources with C flags and link them into the extension.

    One ``Extension`` takes one set of compiler flags, and GCC rejects
    ``-std=c++17`` for a ``.c`` file, so the decoder is compiled here and
    handed to the link as objects.
    """

    def build_extension(self, ext):
        objects = self.compiler.compile(
            C_SOURCES,
            output_dir=self.build_temp,
            extra_postargs=C_FLAGS,
            depends=C_SOURCES,
        )
        ext.extra_objects = list(ext.extra_objects or []) + objects
        super().build_extension(ext)


setup(ext_modules=extensions, cmdclass={'build_ext': build_ext})
