"""Copy the basis_universal transcoder into ``vendor/basis_universal``.

Usage::

    git clone --depth 1 --branch v2_50 https://github.com/BinomialLLC/basis_universal /tmp/bu
    python tools/vendor_basisu.py /tmp/bu

The copy holds the transcoder directory, the single-file Zstandard decoder and
the licence and notice files, unmodified. ``vendor/basis_universal/VERSION``
records the tag and commit the copy was taken from. Nothing from the encoder is
copied.
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
TARGET = HERE.parent / 'vendor' / 'basis_universal'

# Paths relative to the basis_universal checkout. ``zstddeclib.c`` is the
# decoder-only amalgamation of Zstandard; ``zstd.c`` also carries the encoder.
FILES = (
    'LICENSE',
    'NOTICE',
    'zstd/LICENSE',
    'zstd/zstd.h',
    'zstd/zstd_errors.h',
    'zstd/zstddeclib.c',
)
DIRECTORIES = ('transcoder',)


def describe(checkout: pathlib.Path) -> tuple[str, str]:
    """Return the exact tag and the commit hash of ``checkout``."""
    commit = subprocess.run(
        ['git', '-C', str(checkout), 'rev-parse', 'HEAD'],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tag = subprocess.run(
        ['git', '-C', str(checkout), 'describe', '--tags', '--exact-match'],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return tag, commit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('checkout', type=pathlib.Path, help='a basis_universal checkout at a tag')
    args = parser.parse_args(argv)
    checkout = args.checkout.resolve()
    tag, commit = describe(checkout)
    # The copy is assembled beside the target and renamed into place, so an
    # interrupted run leaves the previous copy whole.
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=TARGET.parent) as scratch:
        staged = pathlib.Path(scratch) / 'basis_universal'
        for name in DIRECTORIES:
            shutil.copytree(checkout / name, staged / name)
        for name in FILES:
            (staged / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(checkout / name, staged / name)
        (staged / 'VERSION').write_text(
            'https://github.com/BinomialLLC/basis_universal\ntag %s\ncommit %s\n' % (tag, commit),
            encoding='utf-8',
        )
        retired = pathlib.Path(scratch) / 'previous'
        if TARGET.exists():
            TARGET.rename(retired)
        staged.rename(TARGET)
    print('vendored basis_universal %s (%s) into %s' % (tag, commit, TARGET))
    return 0


if __name__ == '__main__':
    sys.exit(main())
