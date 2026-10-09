"""The target table, checked against the transcoder, and choosing a target."""

from __future__ import annotations

import pytest

from opengl_basisu import Codec, Target, _transcoder, choose_target, preferences

S3TC = 'GL_EXT_texture_compression_s3tc'
BPTC = 'GL_ARB_texture_compression_bptc'
ASTC = 'GL_KHR_texture_compression_astc_ldr'
ETC2 = 'GL_ARB_ES3_compatibility'
SRGB = 'GL_EXT_texture_sRGB'


@pytest.mark.parametrize('target', list(Target))
def test_layout_matches_transcoder(target):
    info = target.info
    assert _transcoder.target_bytes(info.basis) == info.bytes_per_block
    assert _transcoder.target_is_uncompressed(info.basis) is (not info.compressed)
    if info.compressed:
        assert _transcoder.target_block(info.basis) == info.block


@pytest.mark.parametrize('target', list(Target))
def test_every_target_takes_both_glTF_codecs(target):
    for codec in (Codec.ETC1S, Codec.UASTC_LDR_4x4):
        assert _transcoder.target_supported(target.info.basis, codec)


def test_codec_hdr_matches_transcoder():
    for codec in Codec:
        assert _transcoder.codec_hdr(codec) is codec.is_hdr


def test_target_by_name():
    assert Target('bc7') is Target.BC7
    assert Target.ASTC_4x4.value == 'astc_4x4'


def test_nothing_compressed_is_rgba8():
    assert choose_target(set(), codec=Codec.ETC1S) is Target.RGBA8
    assert choose_target(set(), codec=Codec.UASTC_LDR_4x4, has_alpha=True) is Target.RGBA8


def test_desktop_core_bc7():
    assert choose_target(set(), codec=Codec.ETC1S, version=(4, 6)) is Target.BC7
    assert choose_target(set(), codec=Codec.ETC1S, version=(4, 1)) is Target.RGBA8


def test_s3tc_only():
    assert choose_target({S3TC}, codec=Codec.ETC1S) is Target.BC1
    assert choose_target({S3TC}, codec=Codec.ETC1S, has_alpha=True) is Target.BC3


def test_s3tc_srgb_needs_its_extension():
    assert choose_target({S3TC}, srgb=True) is Target.RGBA8
    assert choose_target({S3TC, SRGB}, srgb=True) is Target.BC1


def test_uastc_prefers_astc():
    assert choose_target({ASTC, BPTC}, codec=Codec.UASTC_LDR_4x4) is Target.ASTC_4x4
    assert choose_target({ASTC, BPTC}, codec=Codec.ETC1S) is Target.BC7


def test_desktop_etc2_after_bc():
    assert choose_target({ETC2, S3TC}, codec=Codec.ETC1S, version=(3, 3)) is Target.BC1
    assert choose_target({ETC2}, codec=Codec.ETC1S, version=(3, 3)) is Target.ETC1
    assert choose_target({ETC2}, codec=Codec.ETC1S, version=(3, 3), has_alpha=True) is Target.ETC2


def test_es():
    assert choose_target(set(), codec=Codec.ETC1S, version=(3, 0), es=True) is Target.ETC1
    assert choose_target(set(), codec=Codec.UASTC_LDR_4x4, version=(3, 2), es=True) is (
        Target.ASTC_4x4
    )
    assert choose_target(set(), codec=Codec.ETC1S, version=(2, 0), es=True) is Target.RGBA8


def test_two_channel():
    assert choose_target(set(), version=(3, 3), channels='rg') is Target.BC5
    assert choose_target(set(), version=(3, 3), channels='r') is Target.BC4
    assert preferences(Codec.ETC1S, channels='rg')[0] is Target.BC5


def test_bad_channels():
    with pytest.raises(ValueError, match='channels'):
        preferences(Codec.ETC1S, channels='bgr')


def test_internal_format_without_srgb():
    assert Target.BC4.info.internal_format(srgb=True) == 0x8DBB
    assert Target.RGB565.info.internal_format() == 0x8D62
