# opengl_basisu: Basis Universal transcoding as NumPy arrays

Transcode a KTX 2 file with a Basis Universal payload (ETC1S or UASTC, the two
codecs glTF's `KHR_texture_basisu` allows), or a `.basis` file, to a GPU
texture format: BC1, BC3, BC4, BC5, BC7, ETC1, ETC2 or ASTC 4x4 blocks, or
RGBA8 or RGB565 pixels. Input is a path or bytes; output is a NumPy array with
the OpenGL enums to upload it, as integers. Nothing here imports OpenGL.

```python
import opengl_basisu

texture = opengl_basisu.open('albedo.ktx2')
texture.width, texture.height, texture.levels   # 1024, 1024, 11
texture.codec, texture.srgb, texture.has_alpha  # Codec.ETC1S, True, False

target = opengl_basisu.choose_target(
    extensions,                  # the names the GL context reports
    codec=texture.codec,
    has_alpha=texture.has_alpha,
    srgb=texture.srgb,
    version=(4, 6),
)
for image in texture.transcode_levels(target):
    if image.compressed:
        glCompressedTexImage2D(
            GL_TEXTURE_2D, image.level, image.gl_internal_format,
            image.width, image.height, 0, image.nbytes, image.data,
        )
    else:
        glTexImage2D(
            GL_TEXTURE_2D, image.level, image.gl_internal_format,
            image.width, image.height, 0, image.gl_format, image.gl_type, image.data,
        )
```

NumPy is the only runtime dependency.

## Install

```
pip install opengl_basisu
```

Wheels are published for CPython 3.10 to 3.14 on Linux, Windows and macOS
(arm64 and x86_64). A source build needs Cython and a C++17 compiler.

## What a texture reports

| Attribute | Meaning |
|---|---|
| `container` | `'ktx2'` or `'basis'` |
| `width`, `height` | level 0, in pixels |
| `levels` | mip levels, at least 1 |
| `faces` | 1, or 6 for a cube map |
| `layers`, `is_array` | array layers (at least 1), and whether the file declares an array |
| `codec` | a `Codec`: `ETC1S`, `UASTC_LDR_4x4`, or a newer basis_universal codec |
| `has_alpha` | the file stores alpha |
| `srgb` | the colour space is sRGB rather than linear |
| `is_video`, `y_flipped` | a video's frames are its layers; `y_flipped` is a `.basis` flag |

`texture.transcode(target, level=0, face=0, layer=0)` returns an `Image`.
`transcode_levels(target, face, layer)` returns the mip chain, largest first,
and `images(target)` yields every image in the file.

## Targets

| `Target` | Array | GL internal format (linear / sRGB) | Provided by |
|---|---|---|---|
| `BC1` | (rows, cols, 8) | `0x83F0` / `0x8C4C` | `GL_EXT_texture_compression_s3tc`; sRGB also `GL_EXT_texture_sRGB` |
| `BC3` | (rows, cols, 16) | `0x83F3` / `0x8C4F` | as BC1 |
| `BC4` | (rows, cols, 8) | `0x8DBB` / none | GL 3.0, `GL_ARB_texture_compression_rgtc` |
| `BC5` | (rows, cols, 16) | `0x8DBD` / none | GL 3.0, `GL_ARB_texture_compression_rgtc` |
| `BC7` | (rows, cols, 16) | `0x8E8C` / `0x8E8D` | GL 4.2, `GL_ARB_texture_compression_bptc`, `GL_EXT_texture_compression_bptc` |
| `ETC1` | (rows, cols, 8) | `0x9274` / `0x9275` (ETC2 RGB8) | GL 4.3, GLES 3.0, `GL_ARB_ES3_compatibility` |
| `ETC2` | (rows, cols, 16) | `0x9278` / `0x9279` | GL 4.3, GLES 3.0, `GL_ARB_ES3_compatibility` |
| `ASTC_4x4` | (rows, cols, 16) | `0x93B0` / `0x93D0` | GLES 3.2, `GL_KHR_texture_compression_astc_ldr` |
| `RGBA8` | (height, width, 4) uint8 | `GL_RGBA8` / `GL_SRGB8_ALPHA8` | always |
| `RGB565` | (height, width) uint16 | `GL_RGB565` / none | GL 4.1, GLES 2.0 |

Block arrays are uint8, one 4x4 block per `(row, column)`, rows of blocks top
to bottom; `rows` and `cols` round the pixel size up to whole blocks.
`Target.X.info` is the `TargetFormat` with these values, and
`TargetFormat.available(extensions, version, es, srgb)` answers whether a
context provides it.

`choose_target()` takes the extension names, version and `es` flag of a
context, and the texture's codec, alpha and colour space. It walks
`preferences(codec, es, channels)` and returns the first target the context
provides, or `RGBA8`. On desktop GL the BC formats come before ETC because
desktop drivers commonly decode ETC2 to RGBA8 at upload. UASTC prefers ASTC
4x4, which it transcodes to without re-encoding; ETC1S on GLES prefers ETC1
for the same reason. `channels='r'` or `'rg'` puts BC4 or BC5 first, for
single and two-channel data.

## Errors

- `BasisuError` (a `ValueError`): truncated or corrupt data, or bytes that are
  neither KTX 2 nor `.basis`.
- `UnsupportedError` (a `BasisuError`): a KTX 2 file whose payload is not a
  Basis Universal codec (an uncompressed or a plain BCn KTX 2, for example), or
  a high dynamic range codec asked for an 8-bit target.
- `ValueError`: an unknown target name. `IndexError`: a level, face or layer
  the texture does not have.

The test suite truncates every fixture at every length and transcodes 5,000
randomly corrupted copies of each; corrupt input raises. `docs/API.md` has the
AddressSanitizer run of the same tests.

## Limits

- High dynamic range codecs (UASTC HDR 4x4, ASTC HDR 6x6) open and report
  their header, and have no target here.
- The layers of an ETC1S video are P-frames: transcode them in order from
  layer 0.
- One `Texture` transcodes one image at a time (a lock serialises threads);
  separate textures transcode in parallel with the GIL released.
- The transcoder addresses files of up to 4 GiB.

## The transcoder

The compiled extension is Binomial's
[basis_universal](https://github.com/BinomialLLC/basis_universal) transcoder,
tag `v2_50` (commit `9bebe167`), with the Zstandard decoder it bundles. Both
are copied unmodified into `vendor/basis_universal`; `vendor/basis_universal/VERSION`
records the tag and commit, and `tools/vendor_basisu.py` repeats the copy for
another tag. No encoder code is included.

## Test fixtures

`tests/fixtures` holds six files of under 600 bytes each, written by the
basis_universal `v2_50` encoder from flat-colour images by
`tools/make_fixtures.py`; its docstring has the build and the encoder flags
for each file. `tests/fixtures/colours.json` lists the colours the tests
compare against.

## Licence

This package is MIT licensed (`LICENSE`). The extension also contains the
basis_universal transcoder under the Apache License 2.0
(`vendor/basis_universal/LICENSE`, `vendor/basis_universal/NOTICE`) and the
Zstandard decoder under the BSD licence (`vendor/basis_universal/zstd/LICENSE`).
`NOTICE` lists both.
