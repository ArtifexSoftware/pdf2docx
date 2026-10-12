"""Image policy owned by pdf2docx, before images enter the DOCX package."""

from dataclasses import dataclass
from io import BytesIO
import math
import os

from PIL import Image


def image_defaults():
    """CLI kwargs override these environment-backed defaults."""
    return {
        'clip_image_res_ratio': float(os.getenv('PDF2DOCX_CLIP_IMAGE_RES_RATIO',
            os.getenv('OFFICECLI_PDF_CLIP_IMAGE_RES_RATIO', '1.0'))),
        'image_format': os.getenv('PDF2DOCX_IMAGE_FORMAT', 'preserve'),
        'image_jpeg_quality': int(os.getenv('PDF2DOCX_IMAGE_JPEG_QUALITY', '95')),
        'image_max_dpi': float(os.getenv('PDF2DOCX_IMAGE_MAX_DPI', '0')),
        'image_png_compress_level': int(os.getenv('PDF2DOCX_IMAGE_PNG_COMPRESS_LEVEL', '6')),
    }


@dataclass(frozen=True)
class ImageSettings:
    image_format: str = 'preserve'
    image_jpeg_quality: int = 95
    image_max_dpi: float = 0
    image_png_compress_level: int = 6

    def __post_init__(self):
        if self.image_format not in ('preserve', 'jpeg', 'png'):
            raise ValueError('image_format must be preserve, jpeg or png')
        if (isinstance(self.image_jpeg_quality, bool)
                or not isinstance(self.image_jpeg_quality, int)
                or not 1 <= self.image_jpeg_quality <= 100):
            raise ValueError('image_jpeg_quality must be an integer within 1..100')
        if not math.isfinite(self.image_max_dpi) or self.image_max_dpi < 0:
            raise ValueError('image_max_dpi must be finite and >= 0 (0 keeps native pixels)')
        if (isinstance(self.image_png_compress_level, bool)
                or not isinstance(self.image_png_compress_level, int)
                or not 0 <= self.image_png_compress_level <= 9):
            raise ValueError('image_png_compress_level must be an integer within 0..9')

    @classmethod
    def from_settings(cls, settings):
        return cls(**{key: settings[key] for key in cls.__dataclass_fields__ if key in settings})

    def apply(self, raw, rotation=0):
        """Preserve supported bytes by default; re-encode only for a requested change.

        Alpha is never flattened just to satisfy a JPEG request. Unsupported PDF
        encodings and composited images use PNG because Word cannot embed them.
        """
        with Image.open(BytesIO(raw['image'])) as original:
            source_format = original.format
            target_format = {'jpeg': 'JPEG', 'png': 'PNG'}.get(self.image_format, source_format)
            if target_format not in ('JPEG', 'PNG', 'BMP', 'GIF', 'TIFF'):
                target_format = 'PNG'
            has_alpha = 'A' in original.getbands() or 'transparency' in original.info
            if has_alpha and target_format == 'JPEG':
                target_format = 'PNG'
            width_pt = abs(raw['bbox'][2] - raw['bbox'][0])
            height_pt = abs(raw['bbox'][3] - raw['bbox'][1])
            image = original
            if rotation % 360:
                image = original.rotate(rotation, expand=True)
            scale = 1.0
            if self.image_max_dpi and width_pt and height_pt:
                scale = min(1.0, width_pt * self.image_max_dpi / (72 * image.width),
                            height_pt * self.image_max_dpi / (72 * image.height))
            if scale < 1.0:
                image = image.resize((max(1, round(image.width * scale)),
                                      max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
            unchanged = not rotation % 360 and scale == 1.0 and target_format == source_format
            # Quality 100 reuses an unchanged JPEG; lower quality explicitly recompresses.
            if unchanged and (self.image_format == 'preserve'
                    or (self.image_format == 'jpeg' and self.image_jpeg_quality == 100)):
                return raw
            if target_format == 'JPEG' and image.mode not in ('RGB', 'L'):
                image = image.convert('RGB')
            output = BytesIO()
            options = {'quality': self.image_jpeg_quality, 'optimize': True} if target_format == 'JPEG' else {}
            if target_format == 'PNG':
                options['compress_level'] = self.image_png_compress_level
            image.save(output, format=target_format, **options)
            return {**raw, 'image': output.getvalue(), 'width': image.width, 'height': image.height}


def validate_image_settings(settings):
    ratio = settings['clip_image_res_ratio']
    if not math.isfinite(ratio) or not 0.5 <= ratio <= 4:
        raise ValueError('clip_image_res_ratio must be finite and within 0.5..4')
    ImageSettings.from_settings(settings)
