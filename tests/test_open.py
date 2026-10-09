"""Opening fixtures and reading what they declare."""

from __future__ import annotations

import pathlib

import pytest
from samples import FIXTURES, read

import opengl_basisu
from opengl_basisu import Codec


@pytest.mark.parametrize(
    'name, container, codec, size, levels, faces, srgb, alpha',
    [
        ('etc1s_srgb_mips.ktx2', 'ktx2', Codec.ETC1S, (16, 16), 5, 1, True, False),
        ('uastc_rgba.ktx2', 'ktx2', Codec.UASTC_LDR_4x4, (16, 16), 1, 1, False, True),
        ('uastc_odd.ktx2', 'ktx2', Codec.UASTC_LDR_4x4, (6, 5), 1, 1, False, False),
        ('etc1s_cube.ktx2', 'ktx2', Codec.ETC1S, (8, 8), 1, 6, True, False),
        ('etc1s_rgba.basis', 'basis', Codec.ETC1S, (16, 16), 1, 1, True, True),
        ('uastc_hdr.ktx2', 'ktx2', Codec.UASTC_HDR_4x4, (8, 8), 1, 1, False, False),
    ],
)
def test_header(name, container, codec, size, levels, faces, srgb, alpha):
    texture = opengl_basisu.open(FIXTURES / name)
    assert texture.container == container
    assert texture.codec is codec
    assert (texture.width, texture.height) == size
    assert texture.levels == levels
    assert texture.faces == faces
    assert texture.layers == 1
    assert not texture.is_array
    assert texture.srgb is srgb
    assert texture.has_alpha is alpha
    assert texture.is_video is False


@pytest.mark.parametrize(
    'source',
    [
        lambda: str(FIXTURES / 'uastc_rgba.ktx2'),
        lambda: FIXTURES / 'uastc_rgba.ktx2',
        lambda: read('uastc_rgba.ktx2'),
        lambda: bytearray(read('uastc_rgba.ktx2')),
        lambda: memoryview(read('uastc_rgba.ktx2')),
    ],
    ids=['str', 'path', 'bytes', 'bytearray', 'memoryview'],
)
def test_sources(source):
    assert opengl_basisu.open(source()).width == 16


def test_bytearray_is_copied():
    data = bytearray(read('uastc_rgba.ktx2'))
    texture = opengl_basisu.open(data)
    data[:] = bytes(len(data))
    assert texture.transcode('rgba8').data[0, 0].tolist() == [255, 0, 0, 255]


def test_level_sizes():
    texture = opengl_basisu.open(FIXTURES / 'etc1s_srgb_mips.ktx2')
    assert [texture.level_size(level) for level in range(5)] == [
        (16, 16),
        (8, 8),
        (4, 4),
        (2, 2),
        (1, 1),
    ]


def test_repr():
    texture = opengl_basisu.open(FIXTURES / 'etc1s_cube.ktx2')
    assert repr(texture) == '<Texture ktx2 ETC1S 8x8 levels=1 faces=6 layers=1 sRGB>'


@pytest.mark.parametrize('name', ['etc1s_srgb_mips.ktx2', 'etc1s_rgba.basis'])
def test_container_of(name):
    assert opengl_basisu.container_of(read(name)) == pathlib.Path(name).suffix[1:]


def test_container_of_other():
    assert opengl_basisu.container_of(b'\x89PNG\r\n\x1a\n') is None


def test_supports():
    hdr = opengl_basisu.open(FIXTURES / 'uastc_hdr.ktx2')
    ldr = opengl_basisu.open(FIXTURES / 'uastc_rgba.ktx2')
    assert not hdr.supports('rgba8')
    assert ldr.supports('rgba8')
    assert ldr.supports(opengl_basisu.Target.BC7)


def test_version():
    assert opengl_basisu.BASISU_VERSION in (
        pathlib.Path(__file__).resolve().parent.parent / 'vendor' / 'basis_universal' / 'VERSION'
    ).read_text(encoding='utf-8')
