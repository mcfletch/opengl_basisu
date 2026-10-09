# Changelog

## 0.1.0a1

- `open()` reads a KTX 2 file with an ETC1S or UASTC payload, or a `.basis` file, from a path or bytes.
- `Texture.transcode()` writes BC1, BC3, BC4, BC5, BC7, ETC1, ETC2, ASTC 4x4, RGBA8 or RGB565 as a NumPy array.
- `Target.info` carries each format's GL enums; `choose_target()` picks one from a context's extensions and version.
- Transcoder: basis_universal v2_50 (commit 9bebe167).
