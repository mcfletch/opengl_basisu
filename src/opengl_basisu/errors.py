"""The exceptions :mod:`opengl_basisu` raises."""

from __future__ import annotations

__all__ = ['BasisuError', 'UnsupportedError']


class BasisuError(ValueError):
    """A file the transcoder cannot read: truncated, corrupt, or not KTX 2 or ``.basis``."""


class UnsupportedError(BasisuError):
    """A well-formed file asked for something this package does not do.

    A KTX 2 file whose payload is not a Basis Universal codec, and a request to
    transcode a high dynamic range codec to an 8-bit target, raise this.
    """
