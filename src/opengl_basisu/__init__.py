"""Basis Universal KTX 2 and ``.basis`` transcoding to GPU texture formats.

A KTX 2 file whose payload is ETC1S or UASTC (the two codecs glTF's
``KHR_texture_basisu`` allows), or a ``.basis`` file, opens into a
:class:`Texture`; each of its images transcodes to a block format a GPU
samples directly (BC1, BC3, BC4, BC5, BC7, ETC1, ETC2, ASTC 4x4) or to RGBA8
or RGB565 pixels, as a NumPy array::

    import opengl_basisu

    texture = opengl_basisu.open('albedo.ktx2')
    target = opengl_basisu.choose_target(
        extensions, codec=texture.codec, has_alpha=texture.has_alpha, version=(4, 6)
    )
    for image in texture.transcode_levels(target):
        upload(image.level, image.gl_internal_format, image.width, image.height, image.data)

Nothing here imports OpenGL: each :class:`Target` carries its GL enums as
integers. The transcoder is Binomial's basis_universal, compiled into the
package at the tag in :data:`BASISU_VERSION`.
"""

from opengl_basisu.errors import BasisuError, UnsupportedError
from opengl_basisu.targets import Codec, Target, TargetFormat, choose_target, preferences
from opengl_basisu.texture import Image, Texture, container_of, open

__version__ = '0.1.0a2'

# The basis_universal release the extension is compiled from; the commit is in
# vendor/basis_universal/VERSION.
BASISU_VERSION = 'v2_50'

__all__ = [
    # Reading a file
    'open',
    'Texture',
    'Image',
    'container_of',
    # Choosing what to transcode to
    'Target',
    'TargetFormat',
    'Codec',
    'choose_target',
    'preferences',
    # Refusals
    'BasisuError',
    'UnsupportedError',
    '__version__',
    'BASISU_VERSION',
]
