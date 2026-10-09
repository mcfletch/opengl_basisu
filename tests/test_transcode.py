"""Transcoded images against the colours the fixtures were encoded from."""

from __future__ import annotations

import threading

import blocks
import numpy as np
import pytest
from samples import CUBE_FACES, FIXTURES, QUADRANTS, TRANSLUCENT

import opengl_basisu
from opengl_basisu import Target

# ETC1S and the BC formats quantise a flat colour by a few levels.
TOLERANCE = 6


def quadrant_means(pixels: np.ndarray) -> list[np.ndarray]:
    """Return the mean colour of each quadrant: top-left, top-right, bottom-left, bottom-right."""
    rows, columns = pixels.shape[:2]
    half_r, half_c = rows // 2, columns // 2
    return [
        pixels[:half_r, :half_c].reshape(-1, pixels.shape[2]).mean(axis=0),
        pixels[:half_r, half_c:].reshape(-1, pixels.shape[2]).mean(axis=0),
        pixels[half_r:, :half_c].reshape(-1, pixels.shape[2]).mean(axis=0),
        pixels[half_r:, half_c:].reshape(-1, pixels.shape[2]).mean(axis=0),
    ]


def assert_quadrants(pixels: np.ndarray, expected: list[tuple[int, ...]], channels: int = 4):
    for mean, colour in zip(quadrant_means(pixels), expected, strict=True):
        assert np.abs(mean[:channels] - np.array(colour[:channels])).max() <= TOLERANCE, (
            mean,
            colour,
        )


OPAQUE = list(QUADRANTS)
WITH_ALPHA = list(QUADRANTS[:3]) + [TRANSLUCENT]


@pytest.mark.parametrize(
    'name, expected',
    [
        ('etc1s_srgb_mips.ktx2', OPAQUE),
        ('uastc_rgba.ktx2', WITH_ALPHA),
        ('etc1s_rgba.basis', WITH_ALPHA),
    ],
)
def test_rgba8(name, expected):
    image = opengl_basisu.open(FIXTURES / name).transcode('rgba8')
    assert image.data.shape == (16, 16, 4)
    assert image.data.dtype == np.uint8
    assert not image.compressed
    assert_quadrants(image.data, expected)


def test_uastc_rgba8_is_exact():
    data = opengl_basisu.open(FIXTURES / 'uastc_rgba.ktx2').transcode('rgba8').data
    assert data[0, 0].tolist() == [255, 0, 0, 255]
    assert data[0, 15].tolist() == [0, 255, 0, 255]
    assert data[15, 0].tolist() == [0, 0, 255, 255]
    assert data[15, 15].tolist() == list(TRANSLUCENT)


@pytest.mark.parametrize('name', ['etc1s_srgb_mips.ktx2', 'uastc_rgba.ktx2', 'etc1s_rgba.basis'])
def test_bc1(name):
    image = opengl_basisu.open(FIXTURES / name).transcode(Target.BC1)
    assert image.data.shape == (4, 4, 8)
    assert image.compressed
    assert_quadrants(blocks.decode(image.data, blocks.bc1), OPAQUE, channels=3)


@pytest.mark.parametrize('name', ['uastc_rgba.ktx2', 'etc1s_rgba.basis'])
def test_bc3(name):
    image = opengl_basisu.open(FIXTURES / name).transcode('bc3')
    assert image.data.shape == (4, 4, 16)
    assert_quadrants(blocks.decode(image.data, blocks.bc3), WITH_ALPHA)


def test_bc4_is_red():
    image = opengl_basisu.open(FIXTURES / 'uastc_rgba.ktx2').transcode('bc4')
    assert image.data.shape == (4, 4, 8)
    red = [(colour[0],) for colour in WITH_ALPHA]
    assert_quadrants(blocks.decode(image.data, blocks.bc4), red, channels=1)


def test_bc5_is_red_and_alpha():
    image = opengl_basisu.open(FIXTURES / 'uastc_rgba.ktx2').transcode('bc5')
    red_alpha = [(colour[0], colour[3]) for colour in WITH_ALPHA]
    assert_quadrants(blocks.decode(image.data, blocks.bc5), red_alpha, channels=2)


@pytest.mark.parametrize('target', ['bc7', 'etc1', 'etc2', 'astc_4x4'])
@pytest.mark.parametrize('name', ['etc1s_srgb_mips.ktx2', 'uastc_rgba.ktx2'])
def test_block_grid(name, target):
    """Each 8x8 quadrant is one flat colour, so its four blocks are identical."""
    image = opengl_basisu.open(FIXTURES / name).transcode(target)
    info = Target(target).info
    assert image.data.shape == (4, 4, info.bytes_per_block)
    grid = image.data
    quadrants = [grid[:2, :2], grid[:2, 2:], grid[2:, :2], grid[2:, 2:]]
    for quadrant in quadrants:
        assert (quadrant == quadrant[0, 0]).all()
    assert len({quadrant[0, 0].tobytes() for quadrant in quadrants}) == 4


def test_rgb565():
    image = opengl_basisu.open(FIXTURES / 'uastc_rgba.ktx2').transcode('rgb565')
    assert image.data.shape == (16, 16)
    assert image.data.dtype == np.dtype('<u2')
    assert image.data[0, 0] == 0xF800
    assert image.data[0, 15] == 0x07E0
    assert image.data[15, 0] == 0x001F


def test_mip_chain():
    texture = opengl_basisu.open(FIXTURES / 'etc1s_srgb_mips.ktx2')
    images = texture.transcode_levels('bc7')
    assert [(image.level, image.width, image.height) for image in images] == [
        (0, 16, 16),
        (1, 8, 8),
        (2, 4, 4),
        (3, 2, 2),
        (4, 1, 1),
    ]
    assert [image.data.shape[:2] for image in images] == [(4, 4), (2, 2), (1, 1), (1, 1), (1, 1)]
    rgba = texture.transcode_levels('rgba8')
    assert [image.data.shape for image in rgba][-1] == (1, 1, 4)


def test_cube_faces():
    texture = opengl_basisu.open(FIXTURES / 'etc1s_cube.ktx2')
    for face, colour in enumerate(CUBE_FACES):
        data = texture.transcode('rgba8', face=face).data
        assert np.abs(data.reshape(-1, 4).mean(axis=0) - colour).max() <= TOLERANCE
    assert [image.face for image in texture.images('bc1')] == [0, 1, 2, 3, 4, 5]


def test_off_grid_size():
    texture = opengl_basisu.open(FIXTURES / 'uastc_odd.ktx2')
    assert texture.transcode('rgba8').data.shape == (5, 6, 4)
    assert (texture.transcode('rgba8').data == QUADRANTS[1]).all()
    assert texture.transcode('bc7').data.shape == (2, 2, 16)


def test_image_gl_enums():
    srgb = opengl_basisu.open(FIXTURES / 'etc1s_srgb_mips.ktx2').transcode('bc7')
    linear = opengl_basisu.open(FIXTURES / 'uastc_rgba.ktx2').transcode('bc7')
    assert srgb.gl_internal_format == 0x8E8D
    assert linear.gl_internal_format == 0x8E8C
    assert srgb.gl_format is None
    assert srgb.nbytes == 16 * 16
    pixels = opengl_basisu.open(FIXTURES / 'etc1s_srgb_mips.ktx2').transcode('rgba8')
    assert pixels.gl_internal_format == 0x8C43
    assert (pixels.gl_format, pixels.gl_type) == (0x1908, 0x1401)


def test_threads_share_one_texture():
    texture = opengl_basisu.open(FIXTURES / 'uastc_rgba.ktx2')
    expected = texture.transcode('bc7').data
    results: list[bool] = []

    def work():
        for _ in range(20):
            results.append(bool((texture.transcode('bc7').data == expected).all()))

    threads = [threading.Thread(target=work) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results == [True] * 160
