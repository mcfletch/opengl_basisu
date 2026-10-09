"""Write the test fixtures in ``tests/fixtures`` with basis_universal's encoder.

Usage::

    git clone --depth 1 --branch v2_50 https://github.com/BinomialLLC/basis_universal /tmp/bu
    cmake -S /tmp/bu -B /tmp/bu/build -DCMAKE_BUILD_TYPE=Release && cmake --build /tmp/bu/build
    python tools/make_fixtures.py /tmp/bu/bin/basisu

The source images are flat colours laid out on the 4x4 block grid, so every
block a transcoder writes holds one colour and the tests compare against the
colours listed in ``tests/fixtures/colours.json``. The encoder is the tag in
``vendor/basis_universal/VERSION``; the source PNGs are written to a temporary
directory and are not kept.

Each fixture and the command that made it:

* ``etc1s_srgb_mips.ktx2`` - ETC1S, sRGB, 16x16 quadrants, a full mip chain.
* ``uastc_rgba.ktx2`` - UASTC LDR 4x4, linear, Zstandard supercompressed,
  16x16 quadrants with one translucent quadrant.
* ``uastc_odd.ktx2`` - UASTC LDR 4x4, 6x5 pixels, a size off the block grid.
* ``etc1s_cube.ktx2`` - ETC1S cube map, six 8x8 faces of one colour each.
* ``etc1s_rgba.basis`` - ETC1S with an alpha slice, as a ``.basis`` file.
* ``uastc_hdr.ktx2`` - UASTC HDR 4x4, 8x8, a codec with no 8-bit target.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / 'tests' / 'fixtures'

# Top-left, top-right, bottom-left, bottom-right; rows run top to bottom.
QUADRANTS = (
    (255, 0, 0, 255),
    (0, 255, 0, 255),
    (0, 0, 255, 255),
    (255, 255, 255, 255),
)
TRANSLUCENT = (255, 255, 255, 64)
CUBE_FACES = (
    (255, 0, 0, 255),
    (0, 255, 255, 255),
    (0, 255, 0, 255),
    (255, 0, 255, 255),
    (0, 0, 255, 255),
    (255, 255, 0, 255),
)


def quadrants(size: int, colours: tuple[tuple[int, int, int, int], ...]) -> np.ndarray:
    """Return a ``size`` square RGBA image of four flat quadrants."""
    half = size // 2
    image = np.zeros((size, size, 4), dtype=np.uint8)
    image[:half, :half] = colours[0]
    image[:half, half:] = colours[1]
    image[half:, :half] = colours[2]
    image[half:, half:] = colours[3]
    return image


def flat(width: int, height: int, colour: tuple[int, int, int, int]) -> np.ndarray:
    """Return a ``width`` x ``height`` RGBA image of one colour."""
    image = np.empty((height, width, 4), dtype=np.uint8)
    image[:] = colour
    return image


def save(image: np.ndarray, path: pathlib.Path, alpha: bool = True) -> str:
    """Write ``image`` as a PNG, dropping alpha when ``alpha`` is false."""
    data = image if alpha else image[..., :3]
    Image.fromarray(np.ascontiguousarray(data)).save(path)
    return str(path)


def encode(basisu: str, inputs: list[str], output: pathlib.Path, *flags: str) -> None:
    """Run the encoder on ``inputs`` and write ``output``."""
    command = [basisu, *flags, '-no_multithreading', '-output_file', str(output)]
    for name in inputs:
        command += ['-file', name]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
    print('%s  %d bytes  %s' % (output.name, output.stat().st_size, ' '.join(flags)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('basisu', help='the basisu command-line encoder')
    args = parser.parse_args(argv)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        work = pathlib.Path(scratch)
        opaque = save(quadrants(16, QUADRANTS), work / 'opaque.png', alpha=False)
        translucent = save(quadrants(16, QUADRANTS[:3] + (TRANSLUCENT,)), work / 'translucent.png')
        odd = save(flat(6, 5, QUADRANTS[1]), work / 'odd.png', alpha=False)
        faces = [
            save(flat(8, 8, colour), work / ('face%d.png' % index), alpha=False)
            for index, colour in enumerate(CUBE_FACES)
        ]
        encode(
            args.basisu, [opaque], FIXTURES / 'etc1s_srgb_mips.ktx2', '-ktx2', '-etc1s', '-mipmap'
        )
        encode(
            args.basisu, [translucent], FIXTURES / 'uastc_rgba.ktx2', '-ktx2', '-uastc', '-linear'
        )
        encode(args.basisu, [odd], FIXTURES / 'uastc_odd.ktx2', '-ktx2', '-uastc', '-linear')
        encode(args.basisu, faces, FIXTURES / 'etc1s_cube.ktx2', '-ktx2', '-etc1s', '-cubemap')
        encode(args.basisu, [translucent], FIXTURES / 'etc1s_rgba.basis', '-basis', '-etc1s')
        encode(
            args.basisu,
            [save(flat(8, 8, QUADRANTS[0]), work / 'hdr.png', alpha=False)],
            FIXTURES / 'uastc_hdr.ktx2',
            '-ktx2',
            '-hdr',
        )
    staged = FIXTURES / 'colours.json.partial'
    staged.write_text(
        json.dumps(
            {
                'quadrants': QUADRANTS,
                'translucent': TRANSLUCENT,
                'cube_faces': CUBE_FACES,
            },
            indent=2,
        )
        + '\n',
        encoding='utf-8',
    )
    staged.replace(FIXTURES / 'colours.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
