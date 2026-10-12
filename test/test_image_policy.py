"""Deterministic image tests without LibreOffice or network dependencies."""
import io
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import fitz
from PIL import Image

from pdf2docx import Converter
from pdf2docx.image.ImagesExtractor import ImagesExtractor
from pdf2docx.image.ImageSettings import ImageSettings


def encoded_image(fmt='JPEG', size=(640, 480), alpha=False):
    mode = 'RGBA' if alpha else 'RGB'
    channels = 4 if alpha else 3
    pixels = random.Random(42).randbytes(size[0] * size[1] * channels)
    image = Image.frombytes(mode, size, pixels)
    out = io.BytesIO()
    image.save(out, fmt, quality=80)
    return out.getvalue()


def page_with_image(data, rotate=0):
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.insert_image(fitz.Rect(50, 50, 250, 200), stream=data, rotate=rotate)
    return doc, page


class ImagePolicyTest(unittest.TestCase):
    def test_default_jpeg_preserves_exact_bytes_and_pixels(self):
        data = encoded_image()
        doc, page = page_with_image(data)
        with doc:
            raw = ImagesExtractor(page).extract_images()[0]
        self.assertEqual(data, raw['image'])
        self.assertEqual((640, 480), (raw['width'], raw['height']))

    def test_quality_100_jpeg_reuses_original_stream(self):
        data = encoded_image()
        doc, page = page_with_image(data)
        with doc:
            raw = ImagesExtractor(page, ImageSettings(image_format='jpeg', image_jpeg_quality=100)).extract_images()[0]
        self.assertEqual(data, raw['image'])

    def test_quality_100_uses_full_chroma_for_new_jpeg_encoding(self):
        from PIL.JpegImagePlugin import get_sampling
        doc, page = page_with_image(encoded_image('PNG'))
        with doc:
            raw = ImagesExtractor(page, ImageSettings(image_format='jpeg', image_jpeg_quality=100)).extract_images()[0]
        image = Image.open(io.BytesIO(raw['image']))
        self.assertEqual('JPEG', image.format)
        self.assertEqual(0, get_sampling(image))
        self.assertEqual((640, 480), image.size)

    def test_native_png_preserves_extracted_stream(self):
        doc, page = page_with_image(encoded_image('PNG'))
        with doc:
            source = doc.extract_image(page.get_images()[0][0])['image']
            raw = ImagesExtractor(page).extract_images()[0]
        self.assertEqual(source, raw['image'])
        self.assertEqual('PNG', Image.open(io.BytesIO(raw['image'])).format)

    def test_smasks_remain_transparent_even_with_jpeg_requested(self):
        doc, page = page_with_image(encoded_image('PNG', alpha=True))
        with doc:
            raw = ImagesExtractor(page, ImageSettings(image_format='jpeg')).extract_images()[0]
        image = Image.open(io.BytesIO(raw['image']))
        self.assertEqual('PNG', image.format)
        self.assertEqual('RGBA', image.mode)
        self.assertLess(image.getextrema()[3][0], 255)

    def test_jpeg_compression_is_opt_in_and_reduces_size(self):
        doc, page = page_with_image(encoded_image('PNG'))
        with doc:
            original = ImagesExtractor(page).extract_images()[0]
            compressed = ImagesExtractor(page, ImageSettings(image_format='jpeg', image_jpeg_quality=70)).extract_images()[0]
        self.assertEqual('JPEG', Image.open(io.BytesIO(compressed['image'])).format)
        self.assertLess(len(compressed['image']), len(original['image']) // 3)
        self.assertEqual((640, 480), (compressed['width'], compressed['height']))

    def test_max_dpi_only_downsamples_and_keeps_format(self):
        doc, page = page_with_image(encoded_image())
        with doc:
            raw = ImagesExtractor(page, ImageSettings(image_max_dpi=72)).extract_images()[0]
        self.assertEqual((200, 150), (raw['width'], raw['height']))
        self.assertEqual('JPEG', Image.open(io.BytesIO(raw['image'])).format)
        doc, page = page_with_image(encoded_image(size=(100, 75)))
        with doc:
            raw = ImagesExtractor(page, ImageSettings(image_max_dpi=300)).extract_images()[0]
        self.assertEqual((100, 75), (raw['width'], raw['height']))

    def test_rotation_keeps_jpeg_and_updates_dimensions(self):
        doc, page = page_with_image(encoded_image(), rotate=90)
        with doc:
            raw = ImagesExtractor(page).extract_images()[0]
        self.assertEqual('JPEG', Image.open(io.BytesIO(raw['image'])).format)
        self.assertEqual((480, 640), (raw['width'], raw['height']))

    def test_default_composition_does_not_use_fourfold_rasterization(self):
        doc, page = page_with_image(encoded_image())
        with doc:
            page.insert_image(fitz.Rect(100, 100, 300, 250), stream=encoded_image())
            raw = ImagesExtractor(page).extract_images()[0]
        self.assertEqual((250, 200), (raw['width'], raw['height']))

    def test_vectors_receive_optional_jpeg_policy(self):
        with fitz.open() as doc:
            page = doc.new_page()
            page.draw_circle(fitz.Point(100, 100), 40, fill=(1, 0, 0))
            extractor = ImagesExtractor(page, ImageSettings(image_format='jpeg'))
            raw = extractor.clip_page_to_dict(fitz.Rect(50, 50, 150, 150), rm_image=True)
        self.assertEqual('JPEG', Image.open(io.BytesIO(raw['image'])).format)
        self.assertEqual((100, 100), (raw['width'], raw['height']))

    def test_docx_media_embeds_original_jpeg_without_png_expansion(self):
        data = encoded_image()
        with tempfile.TemporaryDirectory() as tmp:
            pdf, output = Path(tmp) / 'source.pdf', Path(tmp) / 'output.docx'
            doc, page = page_with_image(data)
            page.insert_text((50, 30), 'Image preservation test')
            doc.save(pdf)
            doc.close()
            converter = Converter(str(pdf))
            try:
                converter.convert(str(output), ignore_page_error=False)
            finally:
                converter.close()
            with zipfile.ZipFile(output) as archive:
                media = [name for name in archive.namelist() if name.startswith('word/media/')]
                self.assertEqual(1, len(media))
                self.assertTrue(media[0].endswith('.jpg') or media[0].endswith('.jpeg'))
                self.assertEqual(data, archive.read(media[0]))

    def test_invalid_policy_fails_and_cli_returns_nonzero(self):
        for kwargs in ({'image_format': 'webp'}, {'image_jpeg_quality': 101},
                       {'image_max_dpi': float('nan')}, {'image_png_compress_level': -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ImageSettings(**kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / 'source.pdf'
            doc, _ = page_with_image(encoded_image())
            doc.save(pdf)
            doc.close()
            result = subprocess.run([sys.executable, '-m', 'pdf2docx.main', 'convert', str(pdf),
                                     '--image_format=webp'], capture_output=True)
            self.assertNotEqual(0, result.returncode)
            self.assertIn(b'image_format', result.stderr)

    def test_png_compression_level_is_lossless_and_configurable(self):
        data = io.BytesIO()
        Image.new('RGB', (200, 150), (100, 150, 200)).save(data, 'PNG')
        raw = {'image': data.getvalue(), 'bbox': (0, 0, 200, 150), 'width': 200, 'height': 150}
        fast = ImageSettings(image_format='png', image_png_compress_level=0).apply(raw)
        compact = ImageSettings(image_format='png', image_png_compress_level=9).apply(raw)
        self.assertLess(len(compact['image']), len(fast['image']))
        self.assertEqual(Image.open(io.BytesIO(fast['image'])).tobytes(),
                         Image.open(io.BytesIO(compact['image'])).tobytes())

    def test_cmyk_jpeg_is_converted_to_rgb_png_for_word(self):
        image = Image.new('CMYK', (100, 80), (0, 128, 128, 0))
        data = io.BytesIO()
        image.save(data, 'JPEG')
        doc, page = page_with_image(data.getvalue())
        with doc:
            raw = ImagesExtractor(page).extract_images()[0]
        image = Image.open(io.BytesIO(raw['image']))
        self.assertEqual('PNG', image.format)
        self.assertEqual('RGB', image.mode)

    def test_rotated_alpha_preserves_transparency(self):
        doc, page = page_with_image(encoded_image('PNG', alpha=True), rotate=90)
        with doc:
            raw = ImagesExtractor(page, ImageSettings(image_format='jpeg')).extract_images()[0]
        image = Image.open(io.BytesIO(raw['image']))
        self.assertEqual('RGBA', image.mode)
        self.assertEqual((480, 640), image.size)
        self.assertLess(image.getextrema()[3][0], 255)

    def test_render_failure_restores_page_streams(self):
        doc, page = page_with_image(encoded_image())
        with doc:
            page.insert_text((10, 10), 'Must survive renderer failure')
            before = {xref: doc.xref_stream(xref) for xref in page.get_contents()}
            with patch.object(fitz.Page, 'get_pixmap', side_effect=RuntimeError('render failed')):
                with self.assertRaises(RuntimeError):
                    ImagesExtractor(page).clip_page_to_pixmap()
            self.assertEqual(before, {xref: doc.xref_stream(xref) for xref in page.get_contents()})

    def test_environment_defaults_and_cli_override(self):
        with fitz.open() as doc, tempfile.TemporaryDirectory() as tmp:
            doc.new_page()
            pdf = Path(tmp) / 'source.pdf'
            doc.save(pdf)
            with patch.dict(os.environ, {'PDF2DOCX_IMAGE_FORMAT': 'jpeg',
                                         'PDF2DOCX_IMAGE_JPEG_QUALITY': '70'}):
                converter = Converter(str(pdf))
                try:
                    self.assertEqual('jpeg', converter.default_settings['image_format'])
                    self.assertEqual(70, converter.default_settings['image_jpeg_quality'])
                    converter.convert(str(Path(tmp) / 'output.docx'), image_format='preserve')
                finally:
                    converter.close()


if __name__ == '__main__':
    unittest.main()
