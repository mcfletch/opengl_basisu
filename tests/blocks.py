"""Reference decoders for the BC1, BC3, BC4 and BC5 blocks the tests read back.

Each decodes one block into a (4, 4, channels) uint8 array, following the
block layouts in the Khronos Data Format Specification, sections 19 and 20.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import numpy.typing as npt

Pixels = npt.NDArray[np.uint8]


def _565(value: int) -> tuple[int, int, int]:
    red = (value >> 11) & 0x1F
    green = (value >> 5) & 0x3F
    blue = value & 0x1F
    return (red << 3) | (red >> 2), (green << 2) | (green >> 4), (blue << 3) | (blue >> 2)


def bc1(block: bytes, opaque: bool = False) -> Pixels:
    """Return the RGBA pixels of one BC1 block; ``opaque`` for BC3's colour half."""
    c0 = int.from_bytes(block[0:2], 'little')
    c1 = int.from_bytes(block[2:4], 'little')
    e0 = np.array(_565(c0) + (255,), dtype=np.int32)
    e1 = np.array(_565(c1) + (255,), dtype=np.int32)
    if c0 > c1 or opaque:
        palette = [e0, e1, (2 * e0 + e1) // 3, (e0 + 2 * e1) // 3]
    else:
        palette = [e0, e1, (e0 + e1) // 2, np.zeros(4, dtype=np.int32)]
    bits = int.from_bytes(block[4:8], 'little')
    out = np.empty((4, 4, 4), dtype=np.uint8)
    for index in range(16):
        out[index // 4, index % 4] = palette[(bits >> (2 * index)) & 3]
    return out


def bc4(block: bytes) -> Pixels:
    """Return the single channel of one BC4 block as (4, 4, 1)."""
    a0, a1 = int(block[0]), int(block[1])
    if a0 > a1:
        palette = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
    else:
        palette = [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]
    bits = int.from_bytes(block[2:8], 'little')
    out = np.empty((4, 4, 1), dtype=np.uint8)
    for index in range(16):
        out[index // 4, index % 4, 0] = palette[(bits >> (3 * index)) & 7]
    return out


def bc3(block: bytes) -> Pixels:
    """Return the RGBA pixels of one BC3 block: a BC4 alpha half, a BC1 colour half."""
    out = bc1(block[8:16], opaque=True)
    out[..., 3] = bc4(block[0:8])[..., 0]
    return out


def bc5(block: bytes) -> Pixels:
    """Return the two channels of one BC5 block as (4, 4, 2)."""
    return np.concatenate([bc4(block[0:8]), bc4(block[8:16])], axis=2)


def decode(blocks: npt.NDArray[np.uint8], decoder: Callable[[bytes], Pixels]) -> Pixels:
    """Return the whole image a (rows, columns, bytes) grid of blocks decodes to."""
    rows, columns, _size = blocks.shape
    tiles = [
        [decoder(bytes(blocks[row, column])) for column in range(columns)] for row in range(rows)
    ]
    return np.concatenate([np.concatenate(row, axis=1) for row in tiles], axis=0)
