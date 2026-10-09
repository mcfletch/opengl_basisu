# opengl_basisu API

Everything below is importable from `opengl_basisu`.

## Reading a file

`open(source) -> Texture`
: `source` is a path (`str` or `os.PathLike`) or the file's bytes (`bytes`,
  `bytearray`, `memoryview`; the data is copied). Raises `BasisuError` for data
  that is not a KTX 2 or `.basis` file the transcoder accepts, and
  `UnsupportedError` for a KTX 2 file whose `vkFormat` is set and whose payload
  the transcoder does not read.

`container_of(data) -> 'ktx2' | 'basis' | None`
: The container named by the first 12 bytes, without parsing the rest.

`Texture`
: `container`, `width`, `height`, `levels`, `faces`, `layers`, `is_array`,
  `codec`, `has_alpha`, `srgb`, `is_video`, `y_flipped`, as in the README.

  `level_size(level=0) -> (width, height)` in pixels.

  `supports(target) -> bool`: whether the codec transcodes to `target`.

  `transcode(target, level=0, face=0, layer=0) -> Image`. `target` is a
  `Target` or its value (`'bc7'`). Raises `IndexError` for an index out of
  range, `ValueError` for an unknown target name, `UnsupportedError` for a
  codec and target the transcoder does not pair (any HDR codec with any target
  here), and `BasisuError` when the transcoder rejects the image data.

  `transcode_levels(target, face=0, layer=0) -> list[Image]`, largest first.

  `images(target) -> Iterator[Image]`, by layer, then face, then level.

`Image`
: A frozen dataclass: `target`, `width`, `height` (pixels), `level`, `face`,
  `layer`, `srgb` and `data` (a NumPy array). Properties: `compressed`,
  `gl_internal_format` (the sRGB enum when `srgb` and the target has one),
  `gl_format` and `gl_type` (uncompressed targets only, else `None`) and
  `nbytes` (the `imageSize` argument of `glCompressedTexImage2D`).

## Choosing a target

`Target`
: `BC1`, `BC3`, `BC4`, `BC5`, `BC7`, `ETC1`, `ETC2`, `ASTC_4x4`, `RGBA8`,
  `RGB565`. A `str` enum: `Target('etc2') is Target.ETC2`. `Target.X.info` is
  its `TargetFormat`.

`TargetFormat`
: `basis` (the transcoder's format number), `block` (`(4, 4)`, or `(1, 1)` for
  pixels), `bytes_per_block` (per pixel when uncompressed), `channels`,
  `gl_internal_format`, `gl_srgb_internal_format`, `extensions`, `gl_version`,
  `gles_version`, `srgb_extensions`, `gl_format`, `gl_type`. Properties
  `compressed` and `has_alpha`. `internal_format(srgb=False)` returns the enum
  to upload with. `available(extensions, version=(0, 0), es=False, srgb=False)`
  returns whether a context with those extensions and that version provides
  the format.

`preferences(codec, es=False, channels='rgba') -> tuple[Target, ...]`
: The order `choose_target` tries, ending with `RGBA8`.

`choose_target(extensions, codec=Codec.ETC1S, has_alpha=False, version=(0, 0), es=False, srgb=False, channels='rgba') -> Target`
: The first target in `preferences` the context provides, skipping formats
  without alpha when `has_alpha` is set and formats without an sRGB enum when
  `srgb` is set. Returns `RGBA8` when nothing compressed is available.

`Codec`
: An `IntEnum` of the transcoder's `basis_tex_format` values. `Codec.X.is_hdr`
  is true for `UASTC_HDR_4x4`, `ASTC_HDR_6x6` and `UASTC_HDR_6x6`.

## Errors

`BasisuError(ValueError)`, and its subclass `UnsupportedError`.

## Versions

`__version__` is this package's version. `BASISU_VERSION` is the
basis_universal tag compiled in; `vendor/basis_universal/VERSION` has the
commit.

## Sanitizer run

The fuzz tests in `tests/test_errors.py` corrupt and truncate every fixture.
To run them against an AddressSanitizer and UndefinedBehaviorSanitizer build,
copy the project to a scratch directory, change the non-Windows `CXX_FLAGS`
and `C_FLAGS` in its `setup.py` to `-O1 -g -fsanitize=address,undefined
-fno-omit-frame-pointer`, then:

```
LDFLAGS=-fsanitize=address,undefined python setup.py build_ext --inplace
LD_PRELOAD="$(gcc -print-file-name=libasan.so) $(gcc -print-file-name=libubsan.so)" \
ASAN_OPTIONS=detect_leaks=0 \
UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1:suppressions=ubsan.supp \
PYTHONPATH=src python -m pytest -s tests -o addopts=
```

`ubsan.supp` holds one line, `alignment:basisu_transcoder.cpp`. The UASTC
bit reader in the transcoder loads 16-bit words from odd addresses inside a
block, which x86-64 and arm64 execute; UBSan reports each such load. With that
suppression, 30,000 corrupted copies of each fixture run clean on basis_universal
`v2_50`.
