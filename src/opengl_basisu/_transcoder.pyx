# distutils: language = c++
# cython: language_level=3, boundscheck=False, wraparound=False
"""The basis_universal transcoder, compiled from ``vendor/basis_universal``.

Two classes, :class:`KTX2File` and :class:`BasisFile`, hold one parsed file
each and transcode one image of it into a writable buffer the caller sizes.
Validation, buffer sizing and the public API are in :mod:`opengl_basisu.texture`;
this module only crosses into C++.
"""

from libc.stdint cimport uint8_t, uint32_t


cdef extern from '_shim.hpp' namespace 'opengl_basisu' nogil:
    cdef struct texture_info:
        uint32_t width
        uint32_t height
        uint32_t levels
        uint32_t faces
        uint32_t layers
        uint32_t codec
        uint32_t has_alpha
        uint32_t srgb
        uint32_t is_video
        uint32_t y_flipped

    cdef struct level_info:
        uint32_t width
        uint32_t height
        uint32_t has_alpha

    void initialise() except +
    const char *format_name(uint32_t target) except +
    uint32_t bytes_per_block_or_pixel(uint32_t target) except +
    uint32_t block_width(uint32_t target) except +
    uint32_t block_height(uint32_t target) except +
    bint is_uncompressed(uint32_t target) except +
    bint is_supported(uint32_t target, uint32_t codec) except +
    bint codec_is_hdr(uint32_t codec) except +

    cdef cppclass ktx2_file:
        bint open(const uint8_t *data, uint32_t size) except +
        void info(texture_info &out) except +
        bint start() except +
        bint is_video() except +
        bint level(uint32_t level_index, uint32_t layer, uint32_t face, level_info &out) except +
        bint transcode(
            uint32_t level_index, uint32_t layer, uint32_t face, void *output,
            uint32_t output_size, uint32_t target, uint32_t row_pitch, uint32_t rows
        ) except +

    cdef cppclass basis_file:
        bint open(const uint8_t *data, uint32_t size) except +
        void info(texture_info &out) except +
        bint start() except +
        bint is_video() except +
        bint level(uint32_t level_index, uint32_t layer, uint32_t face, level_info &out) except +
        bint transcode(
            uint32_t level_index, uint32_t layer, uint32_t face, void *output,
            uint32_t output_size, uint32_t target, uint32_t row_pitch, uint32_t rows
        ) except +


initialise()

# The largest file the transcoder's 32-bit sizes can address.
MAX_FILE_SIZE = 0xFFFFFFFF


def target_name(uint32_t target):
    """Return the transcoder's own name for ``target``."""
    return format_name(target).decode('ascii')


def target_bytes(uint32_t target):
    """Return the bytes per block, or per pixel for an uncompressed target."""
    return bytes_per_block_or_pixel(target)


def target_block(uint32_t target):
    """Return the block width and height of ``target``; 1, 1 when uncompressed."""
    return block_width(target), block_height(target)


def target_is_uncompressed(uint32_t target):
    """Return whether ``target`` is a raster of pixels rather than of blocks."""
    return is_uncompressed(target)


def target_supported(uint32_t target, uint32_t codec):
    """Return whether files of ``codec`` transcode to ``target``."""
    return is_supported(target, codec)


def codec_hdr(uint32_t codec):
    """Return whether ``codec`` stores high dynamic range colour."""
    return codec_is_hdr(codec)


cdef tuple _info_tuple(texture_info *info):
    return (
        info.width, info.height, info.levels, info.faces, info.layers, info.codec,
        bool(info.has_alpha), bool(info.srgb), bool(info.is_video), bool(info.y_flipped),
    )


cdef class KTX2File:
    """One KTX 2 file whose payload is a Basis Universal codec."""

    cdef ktx2_file *_file
    cdef bytes _data

    def __cinit__(self, bytes data not None):
        self._file = new ktx2_file()
        self._data = data
        if len(data) > MAX_FILE_SIZE or not self._file.open(<const uint8_t *>data, <uint32_t>len(data)):
            raise ValueError('not a KTX 2 file the transcoder accepts')

    def __dealloc__(self):
        del self._file

    def info(self):
        """Return width, height, levels, faces, layers, codec and four flags."""
        cdef texture_info info
        self._file.info(info)
        return _info_tuple(&info)

    def start(self):
        """Unpack the global data; return whether the file is fit to transcode."""
        return self._file.start()

    def is_video(self):
        """Return whether the layers are the frames of a video."""
        return self._file.is_video()

    def level(self, uint32_t level_index, uint32_t layer, uint32_t face):
        """Return the pixel width, height and alpha flag of one image, or None."""
        cdef level_info info
        if not self._file.level(level_index, layer, face, info):
            return None
        return info.width, info.height, bool(info.has_alpha)

    def transcode(
        self, uint32_t level_index, uint32_t layer, uint32_t face, uint32_t target,
        unsigned char[::1] output, uint32_t output_size, uint32_t row_pitch, uint32_t rows,
    ):
        """Write one image into ``output``; return whether the transcoder succeeded."""
        cdef bint result
        cdef void *pointer = &output[0]
        with nogil:
            result = self._file.transcode(
                level_index, layer, face, pointer, output_size, target, row_pitch, rows
            )
        return result


cdef class BasisFile:
    """One ``.basis`` file."""

    cdef basis_file *_file
    cdef bytes _data

    def __cinit__(self, bytes data not None):
        self._file = new basis_file()
        self._data = data
        if len(data) > MAX_FILE_SIZE or not self._file.open(<const uint8_t *>data, <uint32_t>len(data)):
            raise ValueError('not a .basis file the transcoder accepts')

    def __dealloc__(self):
        del self._file

    def info(self):
        """Return width, height, levels, faces, layers, codec and four flags."""
        cdef texture_info info
        self._file.info(info)
        return _info_tuple(&info)

    def start(self):
        """Unpack the global data; return whether the file is fit to transcode."""
        return self._file.start()

    def is_video(self):
        """Return whether the images are the frames of a video."""
        return self._file.is_video()

    def level(self, uint32_t level_index, uint32_t layer, uint32_t face):
        """Return the pixel width, height and alpha flag of one image, or None."""
        cdef level_info info
        if not self._file.level(level_index, layer, face, info):
            return None
        return info.width, info.height, bool(info.has_alpha)

    def transcode(
        self, uint32_t level_index, uint32_t layer, uint32_t face, uint32_t target,
        unsigned char[::1] output, uint32_t output_size, uint32_t row_pitch, uint32_t rows,
    ):
        """Write one image into ``output``; return whether the transcoder succeeded."""
        cdef bint result
        cdef void *pointer = &output[0]
        with nogil:
            result = self._file.transcode(
                level_index, layer, face, pointer, output_size, target, row_pitch, rows
            )
        return result
