"""Malformed input raises; it never crashes the interpreter."""

from __future__ import annotations

import random
import struct

import pytest
from samples import FILES, FIXTURES, read

import opengl_basisu
from opengl_basisu import BasisuError, Target, UnsupportedError

KTX2_IDENTIFIER = b'\xabKTX 20\xbb\r\n\x1a\n'


def plain_ktx2(vk_format: int = 37) -> bytes:
    """Return a 4x4 uncompressed KTX 2 file, a payload this package does not transcode."""
    level_data = bytes(64)
    dfd = struct.pack('<I', 4)
    header_size = 80 + 24
    header = KTX2_IDENTIFIER + struct.pack(
        '<13I2Q',
        vk_format,
        1,
        4,
        4,
        0,
        0,
        1,
        1,
        0,
        header_size,
        len(dfd),
        0,
        0,
        0,
        0,
    )
    level_index = struct.pack('<3Q', header_size + len(dfd), len(level_data), len(level_data))
    return header + level_index + dfd + level_data


def exercise(data: bytes) -> None:
    """Open ``data`` and transcode everything it declares; let only BasisuError out."""
    try:
        texture = opengl_basisu.open(data)
        if texture.width * texture.height > 4096 * 4096:
            return
        for target in (Target.RGBA8, Target.BC7, Target.ETC1, Target.BC1):
            for image in texture.images(target):
                assert image.data.size
    except BasisuError:
        pass


@pytest.mark.parametrize('name', FILES)
def test_every_truncation(name):
    data = read(name)
    for length in range(len(data)):
        with pytest.raises(BasisuError):
            texture = opengl_basisu.open(data[:length])
            for image in texture.images('rgba8'):
                assert image.data.size


def test_empty():
    with pytest.raises(BasisuError, match=r'not a KTX 2 or \.basis'):
        opengl_basisu.open(b'')


def test_not_a_texture():
    with pytest.raises(BasisuError, match=r'not a KTX 2 or \.basis'):
        opengl_basisu.open(b'\x89PNG\r\n\x1a\n' + bytes(100))


def test_plain_ktx2_is_unsupported():
    with pytest.raises(UnsupportedError, match='vkFormat 37'):
        opengl_basisu.open(plain_ktx2())


def test_hdr_to_8_bit_is_unsupported():
    texture = opengl_basisu.open(FIXTURES / 'uastc_hdr.ktx2')
    with pytest.raises(UnsupportedError, match='high dynamic range'):
        texture.transcode('rgba8')


def test_unknown_target():
    texture = opengl_basisu.open(FIXTURES / 'uastc_rgba.ktx2')
    with pytest.raises(ValueError, match="unknown target 'dxt9'"):
        texture.transcode('dxt9')


@pytest.mark.parametrize(
    'index, message',
    [
        ({'level': 1}, 'level 1 of a texture with 1'),
        ({'face': 1}, 'face 1 of a texture with 1'),
        ({'layer': 1}, 'layer 1 of a texture with 1'),
        ({'level': -1}, 'level -1'),
    ],
)
def test_out_of_range(index, message):
    texture = opengl_basisu.open(FIXTURES / 'uastc_rgba.ktx2')
    with pytest.raises(IndexError, match=message):
        texture.transcode('rgba8', **index)


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        opengl_basisu.open(tmp_path / 'absent.ktx2')


@pytest.mark.parametrize('name', FILES)
def test_fuzz_bytes(name):
    """Overwrite random bytes, a few at a time, and transcode whatever opens."""
    original = read(name)
    generator = random.Random(name)
    for _ in range(5000):
        data = bytearray(original)
        for _ in range(generator.randint(1, 8)):
            data[generator.randrange(len(data))] = generator.randrange(256)
        exercise(bytes(data))


@pytest.mark.parametrize('name', FILES)
def test_fuzz_header_fields(name):
    """Set each 32-bit word of the first 160 bytes to boundary values."""
    original = read(name)
    for offset in range(0, min(160, len(original) - 4), 4):
        for value in (0, 1, 6, 0xFF, 0xFFFF, 0x7FFFFFFF, 0xFFFFFFFF):
            data = bytearray(original)
            data[offset : offset + 4] = struct.pack('<I', value)
            exercise(bytes(data))
