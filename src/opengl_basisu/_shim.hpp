// Plain-typed access to the basis_universal transcoder for _transcoder.pyx.
//
// The transcoder's own headers use templated packed integers and its own
// containers; this header reduces what the Cython module needs to a few
// structs of uint32_t and one class with the same methods for KTX 2 and
// .basis files, so the .pyx declares nothing but plain C types.
#pragma once

#include <stdint.h>
#include <string.h>

#include "basisu_transcoder.h"

namespace opengl_basisu {

struct texture_info {
    uint32_t width;
    uint32_t height;
    uint32_t levels;
    uint32_t faces;
    // 0 when the texture is not an array, as in the KTX 2 header.
    uint32_t layers;
    uint32_t codec;
    uint32_t has_alpha;
    uint32_t srgb;
    uint32_t is_video;
    uint32_t y_flipped;
};

struct level_info {
    uint32_t width;
    uint32_t height;
    uint32_t has_alpha;
};

inline void initialise() { basist::basisu_transcoder_init(); }

inline const char *format_name(uint32_t target) {
    return basist::basis_get_format_name(static_cast<basist::transcoder_texture_format>(target));
}

inline uint32_t bytes_per_block_or_pixel(uint32_t target) {
    return basist::basis_get_bytes_per_block_or_pixel(
        static_cast<basist::transcoder_texture_format>(target));
}

inline uint32_t block_width(uint32_t target) {
    return basist::basis_get_block_width(static_cast<basist::transcoder_texture_format>(target));
}

inline uint32_t block_height(uint32_t target) {
    return basist::basis_get_block_height(static_cast<basist::transcoder_texture_format>(target));
}

inline bool is_uncompressed(uint32_t target) {
    return basist::basis_transcoder_format_is_uncompressed(
        static_cast<basist::transcoder_texture_format>(target));
}

inline bool is_supported(uint32_t target, uint32_t codec) {
    return basist::basis_is_format_supported(
        static_cast<basist::transcoder_texture_format>(target),
        static_cast<basist::basis_tex_format>(codec));
}

inline bool codec_is_hdr(uint32_t codec) {
    return basist::basis_tex_format_is_hdr(static_cast<basist::basis_tex_format>(codec));
}

// One KTX 2 file. The data is borrowed: the caller keeps it alive and
// unchanged for the life of the object.
class ktx2_file {
  public:
    bool open(const uint8_t *data, uint32_t size) {
        if (!m_transcoder.init(data, size)) {
            return false;
        }
        m_started = false;
        return true;
    }

    void info(texture_info &out) const {
        memset(&out, 0, sizeof(out));
        out.width = m_transcoder.get_width();
        out.height = m_transcoder.get_height();
        out.levels = m_transcoder.get_levels();
        out.faces = m_transcoder.get_faces();
        out.layers = m_transcoder.get_layers();
        out.codec = static_cast<uint32_t>(m_transcoder.get_basis_tex_format());
        out.has_alpha = m_transcoder.get_has_alpha() ? 1 : 0;
        out.srgb = m_transcoder.is_srgb() ? 1 : 0;
        out.y_flipped = 0;
    }

    bool start() {
        if (!m_started) {
            m_started = m_transcoder.start_transcoding();
        }
        return m_started;
    }

    bool is_video() const { return m_transcoder.is_video(); }

    bool level(uint32_t level_index, uint32_t layer, uint32_t face, level_info &out) const {
        basist::ktx2_image_level_info info;
        if (!m_transcoder.get_image_level_info(info, level_index, layer, face)) {
            return false;
        }
        out.width = info.m_orig_width;
        out.height = info.m_orig_height;
        out.has_alpha = info.m_alpha_flag ? 1 : 0;
        return true;
    }

    bool transcode(uint32_t level_index, uint32_t layer, uint32_t face, void *output,
                   uint32_t output_size, uint32_t target, uint32_t row_pitch, uint32_t rows) {
        return m_transcoder.transcode_image_level(
            level_index, layer, face, output, output_size,
            static_cast<basist::transcoder_texture_format>(target), 0, row_pitch, rows);
    }

  private:
    basist::ktx2_transcoder m_transcoder;
    bool m_started = false;
};

// One .basis file. A cube map's images run face by face within each layer, so
// image index = layer * faces + face.
class basis_file {
  public:
    bool open(const uint8_t *data, uint32_t size) {
        m_data = data;
        m_size = size;
        m_started = false;
        if (!m_transcoder.validate_header(data, size)) {
            return false;
        }
        basist::basisu_file_info file;
        if (!m_transcoder.get_file_info(data, size, file)) {
            return false;
        }
        if (file.m_total_images == 0) {
            return false;
        }
        basist::basisu_image_info first;
        if (!m_transcoder.get_image_info(data, size, first, 0)) {
            return false;
        }
        memset(&m_info, 0, sizeof(m_info));
        m_info.width = first.m_orig_width;
        m_info.height = first.m_orig_height;
        m_info.levels = file.m_image_mipmap_levels.size() ? file.m_image_mipmap_levels[0] : 0;
        m_info.codec = static_cast<uint32_t>(file.m_tex_format);
        m_info.has_alpha = file.m_has_alpha_slices ? 1 : 0;
        m_info.srgb = file.m_srgb ? 1 : 0;
        m_info.y_flipped = file.m_y_flipped ? 1 : 0;
        m_info.is_video = file.m_tex_type == basist::cBASISTexTypeVideoFrames ? 1 : 0;
        uint32_t images = file.m_total_images;
        switch (file.m_tex_type) {
            case basist::cBASISTexTypeCubemapArray:
                if (images % 6) {
                    return false;
                }
                m_info.faces = 6;
                m_info.layers = images > 6 ? images / 6 : 0;
                break;
            case basist::cBASISTexType2D:
                m_info.faces = 1;
                m_info.layers = images > 1 ? images : 0;
                break;
            default:
                m_info.faces = 1;
                m_info.layers = images;
                break;
        }
        // Every image is required to have the first image's level count, so
        // that levels x faces x layers addresses all of them.
        for (uint32_t index = 0; index < images; ++index) {
            if (index >= file.m_image_mipmap_levels.size() ||
                file.m_image_mipmap_levels[index] != m_info.levels) {
                return false;
            }
        }
        return m_info.levels != 0;
    }

    void info(texture_info &out) const { out = m_info; }

    bool start() {
        if (!m_started) {
            m_started = m_transcoder.start_transcoding(m_data, m_size);
        }
        return m_started;
    }

    bool is_video() const { return m_info.is_video != 0; }

    bool level(uint32_t level_index, uint32_t layer, uint32_t face, level_info &out) const {
        uint32_t total_blocks = 0;
        uint32_t width = 0;
        uint32_t height = 0;
        if (!m_transcoder.get_image_level_desc(m_data, m_size, image(layer, face), level_index,
                                               width, height, total_blocks)) {
            return false;
        }
        out.width = width;
        out.height = height;
        out.has_alpha = m_info.has_alpha;
        return true;
    }

    bool transcode(uint32_t level_index, uint32_t layer, uint32_t face, void *output,
                   uint32_t output_size, uint32_t target, uint32_t row_pitch, uint32_t rows) {
        return m_transcoder.transcode_image_level(
            m_data, m_size, image(layer, face), level_index, output, output_size,
            static_cast<basist::transcoder_texture_format>(target), 0, row_pitch, nullptr,
            rows);
    }

  private:
    uint32_t image(uint32_t layer, uint32_t face) const { return layer * m_info.faces + face; }

    basist::basisu_transcoder m_transcoder;
    const uint8_t *m_data = nullptr;
    uint32_t m_size = 0;
    bool m_started = false;
    texture_info m_info{};
};

}  // namespace opengl_basisu
