"""Opening a Basis Universal file and transcoding its images.

:func:`open` reads a KTX 2 file whose payload is a Basis Universal codec, or a
``.basis`` file, from a path or from bytes, and answers a :class:`Texture`.
:meth:`Texture.transcode` writes one image (a mip level of one face of one
layer) in a chosen :class:`~opengl_basisu.targets.Target` format and answers
an :class:`Image`::

    texture = opengl_basisu.open('albedo.ktx2')
    texture.width, texture.height, texture.levels    # 1024, 1024, 11
    image = texture.transcode('bc7', level=0)
    image.data                  # (256, 256, 16) uint8: rows of 4x4 blocks
    image.gl_internal_format    # GL_COMPRESSED_SRGB_ALPHA_BPTC_UNORM for an sRGB texture

A block format's array is ``(blocks_high, blocks_wide, bytes_per_block)``
uint8. RGBA8 is ``(height, width, 4)`` uint8 and RGB565 ``(height, width)``
uint16. Rows run from the first row stored in the file; KTX 2 stores the top
row first unless its orientation says otherwise.
"""

from __future__ import annotations

import builtins
import os
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from opengl_basisu import _transcoder
from opengl_basisu.errors import BasisuError, UnsupportedError
from opengl_basisu.targets import Codec, Target

if TYPE_CHECKING:
    from typing import TypeAlias

    Source: TypeAlias = str | os.PathLike[str] | bytes | bytearray | memoryview

__all__ = ['KTX2_IDENTIFIER', 'BASIS_SIGNATURE', 'Image', 'Texture', 'container_of', 'open']

KTX2_IDENTIFIER = b'\xabKTX 20\xbb\r\n\x1a\n'
BASIS_SIGNATURE = b'sB'

# The KTX 2 header's vkFormat field, and the formats basis_universal writes
# there: VK_FORMAT_UNDEFINED for ETC1S and UASTC LDR, and ASTC formats for the
# codecs whose blocks are standard ASTC.
_VK_FORMAT_OFFSET = 12
_VK_FORMAT_UNDEFINED = 0


def container_of(data: bytes) -> str | None:
    """Return ``'ktx2'`` or ``'basis'`` from the first bytes of ``data``, else None."""
    if data[:12] == KTX2_IDENTIFIER:
        return 'ktx2'
    if data[:2] == BASIS_SIGNATURE:
        return 'basis'
    return None


@dataclass(frozen=True)
class Image:
    """One transcoded image and what a renderer needs to upload it."""

    target: Target
    width: int
    height: int
    level: int
    face: int
    layer: int
    srgb: bool
    data: npt.NDArray[np.generic]

    @property
    def compressed(self) -> bool:
        """Whether :attr:`data` holds blocks, uploaded with ``glCompressedTexImage2D``."""
        return self.target.info.compressed

    @property
    def gl_internal_format(self) -> int:
        """The GL internal format enum, the sRGB variant for an sRGB texture."""
        return self.target.info.internal_format(self.srgb)

    @property
    def gl_format(self) -> int | None:
        """The ``glTexImage2D`` format of an uncompressed image, else None."""
        return self.target.info.gl_format

    @property
    def gl_type(self) -> int | None:
        """The ``glTexImage2D`` type of an uncompressed image, else None."""
        return self.target.info.gl_type

    @property
    def nbytes(self) -> int:
        """The size of :attr:`data` in bytes, the ``imageSize`` of a compressed upload."""
        return int(self.data.nbytes)


class Texture:
    """One parsed KTX 2 or ``.basis`` file.

    The attributes describe the whole texture: ``width`` and ``height`` of
    level 0 in pixels, ``levels`` (at least 1), ``faces`` (1, or 6 for a cube
    map), ``layers`` (at least 1; ``is_array`` says whether the file declares
    an array), ``codec``, ``has_alpha``, ``srgb`` (the colour space is sRGB
    rather than linear), ``is_video`` and ``y_flipped`` (a ``.basis`` file
    whose rows were flipped at encode time).

    Transcoding one texture from several threads is serialised by a lock;
    separate textures transcode in parallel with the GIL released.
    """

    container: str
    width: int
    height: int
    levels: int
    faces: int
    layers: int
    is_array: bool
    codec: Codec
    has_alpha: bool
    srgb: bool
    is_video: bool
    y_flipped: bool

    def __init__(self, data: bytes) -> None:
        container = container_of(data)
        file: _transcoder.KTX2File | _transcoder.BasisFile
        if container == 'ktx2':
            if len(data) < 80:
                raise BasisuError('truncated KTX 2 file: %d bytes' % len(data))
            try:
                file = _transcoder.KTX2File(data)
            except ValueError as error:
                raise _ktx2_error(data) from error
        elif container == 'basis':
            try:
                file = _transcoder.BasisFile(data)
            except ValueError as error:
                raise BasisuError('not a valid .basis file (%d bytes)' % len(data)) from error
        else:
            raise BasisuError('not a KTX 2 or .basis file: starts %r' % (bytes(data[:12]),))
        self.container = container
        self._file = file
        self._lock = threading.Lock()
        self._started = False
        (
            self.width,
            self.height,
            self.levels,
            self.faces,
            layers,
            codec,
            self.has_alpha,
            self.srgb,
            self.is_video,
            self.y_flipped,
        ) = file.info()
        try:
            self.codec = Codec(codec)
        except ValueError:
            raise UnsupportedError('unknown Basis Universal codec %d' % codec) from None
        self.is_array = layers > 0
        self.layers = max(layers, 1)
        if self.faces not in (1, 6) or not self.levels or not self.width or not self.height:
            raise BasisuError(
                'malformed header: %dx%d, %d levels, %d faces'
                % (self.width, self.height, self.levels, self.faces)
            )

    def __repr__(self) -> str:
        return '<Texture %s %s %dx%d levels=%d faces=%d layers=%d%s>' % (
            self.container,
            self.codec.name,
            self.width,
            self.height,
            self.levels,
            self.faces,
            self.layers,
            ' sRGB' if self.srgb else '',
        )

    def level_size(self, level: int = 0) -> tuple[int, int]:
        """Return the width and height in pixels of mip ``level``."""
        self._check_index(level, 0, 0)
        return max(self.width >> level, 1), max(self.height >> level, 1)

    def supports(self, target: Target | str) -> bool:
        """Return whether this texture's codec transcodes to ``target``."""
        return bool(_transcoder.target_supported(Target(target).info.basis, int(self.codec)))

    def transcode(
        self,
        target: Target | str,
        level: int = 0,
        face: int = 0,
        layer: int = 0,
    ) -> Image:
        """Return mip ``level`` of ``face`` of ``layer`` transcoded to ``target``."""
        target = _target(target)
        self._check_index(level, face, layer)
        info = target.info
        if not _transcoder.target_supported(info.basis, int(self.codec)):
            if self.codec.is_hdr:
                raise UnsupportedError(
                    '%s is a high dynamic range codec and has no %s transcode'
                    % (self.codec.name, target.name)
                )
            raise UnsupportedError('%s does not transcode to %s' % (self.codec.name, target.name))
        with self._lock:
            self._start()
            size = self._file.level(level, layer, face)
            if size is None:
                raise BasisuError('no image at level %d, face %d, layer %d' % (level, face, layer))
            width, height, _alpha = size
            block_width, block_height = info.block
            columns = -(-width // block_width)
            rows = -(-height // block_height)
            if info.compressed:
                output = np.zeros((rows, columns, info.bytes_per_block), dtype=np.uint8)
                count, pitch, pixel_rows = rows * columns, 0, 0
            else:
                output = np.zeros((height, width, info.bytes_per_block), dtype=np.uint8)
                count, pitch, pixel_rows = width * height, width, height
            if not self._file.transcode(
                level,
                layer,
                face,
                info.basis,
                output.reshape(-1),
                count,
                pitch,
                pixel_rows,
            ):
                raise BasisuError(
                    'the transcoder rejected level %d, face %d, layer %d as %s'
                    % (level, face, layer, target.name)
                )
        data: npt.NDArray[np.generic] = output
        if target is Target.RGB565:
            data = output.view('<u2').reshape(height, width)
        return Image(
            target=target,
            width=width,
            height=height,
            level=level,
            face=face,
            layer=layer,
            srgb=self.srgb,
            data=data,
        )

    def transcode_levels(self, target: Target | str, face: int = 0, layer: int = 0) -> list[Image]:
        """Return every mip level of ``face`` of ``layer``, largest first."""
        return [self.transcode(target, level, face, layer) for level in range(self.levels)]

    def images(self, target: Target | str) -> Iterator[Image]:
        """Yield every image: by layer, then face, then level from the largest."""
        for layer in range(self.layers):
            for face in range(self.faces):
                yield from self.transcode_levels(target, face, layer)

    def _check_index(self, level: int, face: int, layer: int) -> None:
        if not 0 <= level < self.levels:
            raise IndexError('level %d of a texture with %d' % (level, self.levels))
        if not 0 <= face < self.faces:
            raise IndexError('face %d of a texture with %d' % (face, self.faces))
        if not 0 <= layer < self.layers:
            raise IndexError('layer %d of a texture with %d' % (layer, self.layers))

    def _start(self) -> None:
        if not self._started:
            if not self._file.start():
                raise BasisuError('the global codebooks or tables of the file are corrupt')
            self._started = True


def _target(target: Target | str) -> Target:
    try:
        return Target(target)
    except ValueError:
        raise ValueError(
            'unknown target %r; one of %s' % (target, ', '.join(t.value for t in Target))
        ) from None


def _ktx2_error(data: bytes) -> BasisuError:
    """Return the error for a KTX 2 file the transcoder refused."""
    vk_format = int.from_bytes(data[_VK_FORMAT_OFFSET : _VK_FORMAT_OFFSET + 4], 'little')
    if vk_format != _VK_FORMAT_UNDEFINED:
        return UnsupportedError(
            'KTX 2 file with vkFormat %d holds no Basis Universal payload' % vk_format
        )
    return BasisuError('not a valid Basis Universal KTX 2 file (%d bytes)' % len(data))


def open(source: Source) -> Texture:
    """Return the :class:`Texture` in a file path or in bytes."""
    if isinstance(source, (bytes, bytearray, memoryview)):
        data = bytes(source)
    else:
        with builtins.open(os.fspath(source), 'rb') as handle:
            data = handle.read()
    return Texture(data)
