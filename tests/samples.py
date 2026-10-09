"""Fixture files and the colours they were encoded from."""

from __future__ import annotations

import json
import pathlib

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures'
COLOURS = json.loads((FIXTURES / 'colours.json').read_text(encoding='utf-8'))
QUADRANTS = [tuple(colour) for colour in COLOURS['quadrants']]
TRANSLUCENT = tuple(COLOURS['translucent'])
CUBE_FACES = [tuple(colour) for colour in COLOURS['cube_faces']]

# Every fixture the encoder wrote; see tools/make_fixtures.py.
FILES = (
    'etc1s_srgb_mips.ktx2',
    'uastc_rgba.ktx2',
    'uastc_odd.ktx2',
    'etc1s_cube.ktx2',
    'etc1s_rgba.basis',
    'uastc_hdr.ktx2',
)


def read(name: str) -> bytes:
    """Return the bytes of fixture ``name``."""
    return (FIXTURES / name).read_bytes()
