"""The GPU formats a Basis Universal texture transcodes to, and their GL enums.

Each :class:`Target` names one format the transcoder writes. Its
:attr:`~Target.info` is a :class:`TargetFormat`: the block size, the bytes per
block, the OpenGL internal format enums (linear and sRGB) and the extensions or
core versions that provide them. The enums are plain integers, so a renderer
reads them without this package importing OpenGL::

    >>> from opengl_basisu import Target
    >>> hex(Target.BC7.info.gl_internal_format)
    '0x8e8c'
    >>> hex(Target.BC7.info.gl_srgb_internal_format)
    '0x8e8d'

:func:`choose_target` picks a target from the extension names a context
reports::

    >>> from opengl_basisu import Codec, choose_target
    >>> choose_target({'GL_ARB_texture_compression_bptc'}, codec=Codec.UASTC_LDR_4x4)
    <Target.BC7: 'bc7'>
    >>> choose_target(set(), codec=Codec.ETC1S, version=(3, 3))
    <Target.RGBA8: 'rgba8'>
"""

from __future__ import annotations

import enum
from collections.abc import Collection, Iterable
from dataclasses import dataclass

__all__ = ['Codec', 'Target', 'TargetFormat', 'choose_target', 'preferences']


class Codec(enum.IntEnum):
    """The codec a Basis Universal file stores its images in.

    The values are the transcoder's ``basis_tex_format``. ``ETC1S`` and
    ``UASTC_LDR_4x4`` are the two ``KHR_texture_basisu`` allows; the others
    are newer basis_universal codecs the same transcoder reads.
    """

    ETC1S = 0
    UASTC_LDR_4x4 = 1
    UASTC_HDR_4x4 = 2
    ASTC_HDR_6x6 = 3
    UASTC_HDR_6x6 = 4
    XUASTC_LDR_4x4 = 5
    XUASTC_LDR_5x4 = 6
    XUASTC_LDR_5x5 = 7
    XUASTC_LDR_6x5 = 8
    XUASTC_LDR_6x6 = 9
    XUASTC_LDR_8x5 = 10
    XUASTC_LDR_8x6 = 11
    XUASTC_LDR_10x5 = 12
    XUASTC_LDR_10x6 = 13
    XUASTC_LDR_8x8 = 14
    XUASTC_LDR_10x8 = 15
    XUASTC_LDR_10x10 = 16
    XUASTC_LDR_12x10 = 17
    XUASTC_LDR_12x12 = 18
    ASTC_LDR_4x4 = 19
    ASTC_LDR_5x4 = 20
    ASTC_LDR_5x5 = 21
    ASTC_LDR_6x5 = 22
    ASTC_LDR_6x6 = 23
    ASTC_LDR_8x5 = 24
    ASTC_LDR_8x6 = 25
    ASTC_LDR_10x5 = 26
    ASTC_LDR_10x6 = 27
    ASTC_LDR_8x8 = 28
    ASTC_LDR_10x8 = 29
    ASTC_LDR_10x10 = 30
    ASTC_LDR_12x10 = 31
    ASTC_LDR_12x12 = 32
    XUBC7 = 33

    @property
    def is_hdr(self) -> bool:
        """Whether the codec stores high dynamic range colour."""
        return self in (Codec.UASTC_HDR_4x4, Codec.ASTC_HDR_6x6, Codec.UASTC_HDR_6x6)


@dataclass(frozen=True)
class TargetFormat:
    """One GPU format: its layout, its GL enums and what provides it.

    ``block`` is the block width and height in pixels, ``(1, 1)`` for an
    uncompressed raster, and ``bytes_per_block`` is per pixel there.
    ``gl_format`` and ``gl_type`` are the ``glTexImage2D`` format and type of
    an uncompressed target and ``None`` for a block format, which uploads
    through ``glCompressedTexImage2D``. ``gl_srgb_internal_format`` is
    ``None`` where the format has no sRGB variant.

    A context provides the format when it reports one of ``extensions``, or
    when its version reaches ``gl_version`` (desktop) or ``gles_version``
    (OpenGL ES). The sRGB enum additionally needs one of ``srgb_extensions``
    when that tuple is not empty.
    """

    basis: int
    block: tuple[int, int]
    bytes_per_block: int
    channels: str
    gl_internal_format: int
    gl_srgb_internal_format: int | None
    extensions: tuple[str, ...]
    gl_version: tuple[int, int] | None
    gles_version: tuple[int, int] | None
    srgb_extensions: tuple[str, ...] = ()
    gl_format: int | None = None
    gl_type: int | None = None

    @property
    def compressed(self) -> bool:
        """Whether the format is a grid of blocks rather than of pixels."""
        return self.block != (1, 1)

    @property
    def has_alpha(self) -> bool:
        """Whether the format stores an alpha channel."""
        return 'a' in self.channels

    def internal_format(self, srgb: bool = False) -> int:
        """Return the GL internal format enum, the sRGB one when ``srgb`` is set.

        A format with no sRGB variant answers its linear enum; a renderer
        sampling such a texture as colour applies the transfer function itself.
        """
        if srgb and self.gl_srgb_internal_format is not None:
            return self.gl_srgb_internal_format
        return self.gl_internal_format

    def available(
        self,
        extensions: Collection[str],
        version: tuple[int, int] = (0, 0),
        es: bool = False,
        srgb: bool = False,
    ) -> bool:
        """Return whether a context with these extensions and version provides the format."""
        core = self.gles_version if es else self.gl_version
        provided = (core is not None and tuple(version) >= core) or any(
            name in extensions for name in self.extensions
        )
        if not provided:
            return False
        if srgb and self.srgb_extensions:
            return any(name in extensions for name in self.srgb_extensions)
        return True


# GL enum values, from the Khronos registry (gl.xml).
_GL_RGBA = 0x1908
_GL_RGB = 0x1907
_GL_UNSIGNED_BYTE = 0x1401
_GL_UNSIGNED_SHORT_5_6_5 = 0x8363

_S3TC = ('GL_EXT_texture_compression_s3tc', 'GL_NV_texture_compression_s3tc')
_S3TC_SRGB = ('GL_EXT_texture_sRGB', 'GL_EXT_texture_compression_s3tc_srgb', 'GL_NV_sRGB_formats')
_RGTC = ('GL_ARB_texture_compression_rgtc', 'GL_EXT_texture_compression_rgtc')
_BPTC = ('GL_ARB_texture_compression_bptc', 'GL_EXT_texture_compression_bptc')
_ETC2 = ('GL_ARB_ES3_compatibility',)
_ASTC = ('GL_KHR_texture_compression_astc_ldr', 'GL_OES_texture_compression_astc')


class Target(str, enum.Enum):
    """A format the transcoder writes; ``Target('bc7')`` and ``Target.BC7`` are the same."""

    BC1 = 'bc1'
    BC3 = 'bc3'
    BC4 = 'bc4'
    BC5 = 'bc5'
    BC7 = 'bc7'
    ETC1 = 'etc1'
    ETC2 = 'etc2'
    ASTC_4x4 = 'astc_4x4'
    RGBA8 = 'rgba8'
    RGB565 = 'rgb565'

    @property
    def info(self) -> TargetFormat:
        """The format's layout, GL enums and availability."""
        return _FORMATS[self]


_FORMATS: dict[Target, TargetFormat] = {
    Target.BC1: TargetFormat(
        basis=2,
        block=(4, 4),
        bytes_per_block=8,
        channels='rgb',
        gl_internal_format=0x83F0,  # GL_COMPRESSED_RGB_S3TC_DXT1_EXT
        gl_srgb_internal_format=0x8C4C,  # GL_COMPRESSED_SRGB_S3TC_DXT1_EXT
        extensions=_S3TC + ('GL_EXT_texture_compression_dxt1',),
        gl_version=None,
        gles_version=None,
        srgb_extensions=_S3TC_SRGB,
    ),
    Target.BC3: TargetFormat(
        basis=3,
        block=(4, 4),
        bytes_per_block=16,
        channels='rgba',
        gl_internal_format=0x83F3,  # GL_COMPRESSED_RGBA_S3TC_DXT5_EXT
        gl_srgb_internal_format=0x8C4F,  # GL_COMPRESSED_SRGB_ALPHA_S3TC_DXT5_EXT
        extensions=_S3TC,
        gl_version=None,
        gles_version=None,
        srgb_extensions=_S3TC_SRGB,
    ),
    Target.BC4: TargetFormat(
        basis=4,
        block=(4, 4),
        bytes_per_block=8,
        channels='r',
        gl_internal_format=0x8DBB,  # GL_COMPRESSED_RED_RGTC1
        gl_srgb_internal_format=None,
        extensions=_RGTC,
        gl_version=(3, 0),
        gles_version=None,
    ),
    Target.BC5: TargetFormat(
        basis=5,
        block=(4, 4),
        bytes_per_block=16,
        channels='rg',
        gl_internal_format=0x8DBD,  # GL_COMPRESSED_RG_RGTC2
        gl_srgb_internal_format=None,
        extensions=_RGTC,
        gl_version=(3, 0),
        gles_version=None,
    ),
    Target.BC7: TargetFormat(
        basis=6,
        block=(4, 4),
        bytes_per_block=16,
        channels='rgba',
        gl_internal_format=0x8E8C,  # GL_COMPRESSED_RGBA_BPTC_UNORM
        gl_srgb_internal_format=0x8E8D,  # GL_COMPRESSED_SRGB_ALPHA_BPTC_UNORM
        extensions=_BPTC,
        gl_version=(4, 2),
        gles_version=None,
    ),
    # ETC1 blocks are valid ETC2 RGB8 blocks, so the ETC2 enums (which have an
    # sRGB variant) carry them.
    Target.ETC1: TargetFormat(
        basis=0,
        block=(4, 4),
        bytes_per_block=8,
        channels='rgb',
        gl_internal_format=0x9274,  # GL_COMPRESSED_RGB8_ETC2
        gl_srgb_internal_format=0x9275,  # GL_COMPRESSED_SRGB8_ETC2
        extensions=_ETC2,
        gl_version=(4, 3),
        gles_version=(3, 0),
    ),
    Target.ETC2: TargetFormat(
        basis=1,
        block=(4, 4),
        bytes_per_block=16,
        channels='rgba',
        gl_internal_format=0x9278,  # GL_COMPRESSED_RGBA8_ETC2_EAC
        gl_srgb_internal_format=0x9279,  # GL_COMPRESSED_SRGB8_ALPHA8_ETC2_EAC
        extensions=_ETC2,
        gl_version=(4, 3),
        gles_version=(3, 0),
    ),
    Target.ASTC_4x4: TargetFormat(
        basis=10,
        block=(4, 4),
        bytes_per_block=16,
        channels='rgba',
        gl_internal_format=0x93B0,  # GL_COMPRESSED_RGBA_ASTC_4x4_KHR
        gl_srgb_internal_format=0x93D0,  # GL_COMPRESSED_SRGB8_ALPHA8_ASTC_4x4_KHR
        extensions=_ASTC,
        gl_version=None,
        gles_version=(3, 2),
    ),
    Target.RGBA8: TargetFormat(
        basis=13,
        block=(1, 1),
        bytes_per_block=4,
        channels='rgba',
        gl_internal_format=0x8058,  # GL_RGBA8
        gl_srgb_internal_format=0x8C43,  # GL_SRGB8_ALPHA8
        extensions=(),
        gl_version=(0, 0),
        gles_version=(0, 0),
        gl_format=_GL_RGBA,
        gl_type=_GL_UNSIGNED_BYTE,
    ),
    Target.RGB565: TargetFormat(
        basis=14,
        block=(1, 1),
        bytes_per_block=2,
        channels='rgb',
        gl_internal_format=0x8D62,  # GL_RGB565
        gl_srgb_internal_format=None,
        extensions=(),
        gl_version=(4, 1),
        gles_version=(2, 0),
        gl_format=_GL_RGB,
        gl_type=_GL_UNSIGNED_SHORT_5_6_5,
    ),
}

# Most preferred first. ETC1S transcodes to ETC1 by copying its blocks and to
# the others by re-encoding; UASTC transcodes to ASTC 4x4 by copying and to
# BC7 at nearly the same quality. Desktop drivers that report ETC2 through
# GL_ARB_ES3_compatibility commonly decode it to RGBA8 on upload, so on
# desktop the BC formats come first.
_DESKTOP_ETC1S = (Target.BC7, Target.BC1, Target.BC3, Target.ASTC_4x4, Target.ETC1, Target.ETC2)
_DESKTOP_UASTC = (Target.ASTC_4x4, Target.BC7, Target.BC3, Target.BC1, Target.ETC2, Target.ETC1)
_ES_ETC1S = (Target.ETC1, Target.ETC2, Target.BC7, Target.ASTC_4x4, Target.BC1, Target.BC3)
_ES_UASTC = (Target.ASTC_4x4, Target.BC7, Target.ETC2, Target.ETC1, Target.BC3, Target.BC1)
_RED = (Target.BC4,)
_RED_GREEN = (Target.BC5,)


def preferences(codec: Codec, es: bool = False, channels: str = 'rgba') -> tuple[Target, ...]:
    """Return the targets for ``codec`` in order of preference, ending with RGBA8.

    ``channels`` is ``'r'`` or ``'rg'`` for single and two-channel data, such
    as a roughness map or a two-component normal map, which then prefers
    BC4 or BC5 before the colour formats.
    """
    if codec == Codec.ETC1S:
        colour = _ES_ETC1S if es else _DESKTOP_ETC1S
    else:
        colour = _ES_UASTC if es else _DESKTOP_UASTC
    lead: tuple[Target, ...] = ()
    if channels == 'r':
        lead = _RED
    elif channels == 'rg':
        lead = _RED_GREEN
    elif channels not in ('rgb', 'rgba'):
        raise ValueError('channels is one of r, rg, rgb, rgba, not %r' % (channels,))
    return lead + colour + (Target.RGBA8,)


def choose_target(
    extensions: Iterable[str],
    codec: Codec = Codec.ETC1S,
    has_alpha: bool = False,
    version: tuple[int, int] = (0, 0),
    es: bool = False,
    srgb: bool = False,
    channels: str = 'rgba',
) -> Target:
    """Return the best target a context provides for one texture.

    ``extensions`` are the names the context reports and ``version`` its
    major and minor version; ``es`` says it is OpenGL ES. A texture with
    ``has_alpha`` skips the formats that drop alpha (BC1, ETC1, BC4, BC5), and
    one sampled as ``srgb`` skips the formats whose sRGB enum the context
    lacks. RGBA8 is always available, so a context with no compressed format
    answers it. High dynamic range codecs have no target here.
    """
    names = frozenset(extensions)
    for target in preferences(Codec(codec), es=es, channels=channels):
        info = target.info
        if has_alpha and not info.has_alpha and channels in ('rgb', 'rgba'):
            continue
        if srgb and info.gl_srgb_internal_format is None and channels in ('rgb', 'rgba'):
            continue
        if info.available(names, version, es=es, srgb=srgb):
            return target
    return Target.RGBA8
