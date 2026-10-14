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


def page_with_gray_image(image, bits_per_component=8, rotate=0):
    """Build explicit PDF gray samples; insert_image may auto-index a PNG."""
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    xref = doc.get_new_xref()
    doc.update_object(xref, f'<< /Type /XObject /Subtype /Image /Width {image.width}'
                           f' /Height {image.height} /ColorSpace /DeviceGray'
                           f' /BitsPerComponent {bits_per_component} >>')
    doc.update_stream(xref, image.tobytes())
    page.insert_image(fitz.Rect(50, 50, 250, 200), xref=xref, rotate=rotate)
    return doc, page


def page_with_jpeg_soft_mask(jpeg, samples, inverted=False):
    doc, page = page_with_image(jpeg)
    with Image.open(io.BytesIO(jpeg)) as image:
        width, height = image.size
    image_xref = page.get_images()[0][0]
    mask = doc.get_new_xref()
    decode = '/Decode [1 0]' if inverted else ''
    doc.update_object(mask, f'<< /Type /XObject /Subtype /Image /Width {width}'
                           f' /Height {height} /ColorSpace /DeviceGray'
                           f' /BitsPerComponent 8 {decode} >>')
    doc.update_stream(mask, samples, compress=True)
    doc.xref_set_key(image_xref, 'SMask', f'{mask} 0 R')
    data = doc.tobytes()
    doc.close()
    reopened = fitz.open(stream=data, filetype='pdf')
    return reopened, reopened[0]


class ImagePolicyTest(unittest.TestCase):
    def test_fully_opaque_soft_mask_keeps_native_jpeg_without_rgb_composition(self):
        jpeg = encoded_image()
        for inverted in (False, True):
            with self.subTest(inverted=inverted):
                samples = bytes([0 if inverted else 255]) * (640 * 480)
                doc, page = page_with_jpeg_soft_mask(jpeg, samples, inverted)
                with doc, patch.object(ImagesExtractor, '_recover_pixmap',
                                       side_effect=AssertionError('opaque mask needs no RGB composition')):
                    raw = ImagesExtractor(page).extract_images()[0]
                self.assertEqual(jpeg, raw['image'])
                self.assertEqual((640, 480), (raw['width'], raw['height']))

    def test_almost_opaque_soft_mask_retains_exact_transparency(self):
        jpeg = encoded_image()
        for samples, minimum in ((b'\xff' * (640 * 480 - 1) + b'\x00', 0),
                                 (b'\xfe' * (640 * 480), 254)):
            with self.subTest(minimum=minimum):
                doc, page = page_with_jpeg_soft_mask(jpeg, samples)
                with doc:
                    raw = ImagesExtractor(page).extract_images()[0]
                with Image.open(io.BytesIO(raw['image'])) as image:
                    self.assertEqual('PNG', image.format)
                    self.assertEqual('RGBA', image.mode)
                    self.assertEqual((640, 480), image.size)
                    self.assertEqual(minimum, image.getextrema()[3][0])

    def test_docx_with_opaque_soft_mask_embeds_exact_jpeg_bytes(self):
        jpeg = encoded_image()
        with tempfile.TemporaryDirectory() as tmp:
            pdf, output = Path(tmp) / 'opaque.pdf', Path(tmp) / 'opaque.docx'
            doc, _ = page_with_jpeg_soft_mask(jpeg, b'\xff' * (640 * 480))
            with doc:
                doc.save(pdf)
            converter = Converter(str(pdf))
            try:
                converter.convert(str(output), image_format='preserve', ignore_page_error=False)
            finally:
                converter.close()
            with zipfile.ZipFile(output) as archive:
                media = [archive.read(n) for n in archive.namelist() if n.startswith('word/media/')]
            self.assertEqual([jpeg], media)

    def test_single_image_placement_avoids_pixel_hash_decoding(self):
        data = encoded_image()
        doc, page = page_with_image(data, rotate=90)
        with doc, patch.object(fitz.Page, 'get_image_rects',
                               side_effect=AssertionError('pixel hashing is unnecessary')):
            raw = ImagesExtractor(page).extract_images()[0]
        self.assertEqual(data, raw['image'])
        self.assertEqual((640, 480), (raw['width'], raw['height']))
        self.assertEqual(270, raw['rotation'])

    def test_form_image_uses_complete_occurrence_lookup(self):
        data = encoded_image()
        source, _ = page_with_image(data)
        doc = fitz.open()
        page = doc.new_page(width=400, height=400)
        page.show_pdf_page(page.rect, source, 0)
        original = fitz.Page.get_image_rects
        with source, doc, patch.object(fitz.Page, 'get_image_rects', autospec=True,
                                      side_effect=original) as lookup:
            raw = ImagesExtractor(page).extract_images()
        self.assertEqual(1, len(raw))
        self.assertEqual(data, raw[0]['image'])
        self.assertEqual(1, lookup.call_count)

    def test_repeated_image_preserves_all_occurrences_with_one_lookup(self):
        data = encoded_image()
        doc, page = page_with_image(data)
        page.insert_image(fitz.Rect(50, 250, 250, 400), stream=data)
        original = fitz.Page.get_image_rects
        with doc, patch.object(fitz.Page, 'get_image_rects', autospec=True,
                               side_effect=original) as lookup:
            raw = ImagesExtractor(page).extract_images()
        self.assertEqual(2, len(raw))
        for image in raw:
            self.assertEqual(data, image['image'])
        self.assertEqual(1, lookup.call_count)
        self.assertTrue(lookup.call_args.kwargs['transform'])

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

    def test_binary_pdf_scan_keeps_one_bit_depth_and_exact_pixels(self):
        image = Image.frombytes('1', (1024, 768), random.Random(23).randbytes(128 * 768))
        doc, page = page_with_gray_image(image, bits_per_component=1, rotate=90)
        with doc:
            item = page.get_images()[0]
            self.assertEqual(1, item[4])
            expanded = doc.extract_image(item[0])['image']
            raw = ImagesExtractor(page).extract_images()[0]
        restored = Image.open(io.BytesIO(raw['image']))
        self.assertEqual('PNG', restored.format)
        self.assertEqual('1', restored.mode)
        self.assertEqual(image.size, restored.size)
        self.assertEqual(image.convert('L').tobytes(), restored.convert('L').tobytes())
        self.assertLess(len(raw['image']), len(expanded))
        self.assertEqual(270, raw['rotation'])

    def test_eight_bit_gray_png_keeps_original_bytes_even_when_binary(self):
        image = Image.new('L', (640, 480), 255)
        image.paste(0, (100, 100, 300, 300))
        doc, page = page_with_gray_image(image)
        with doc:
            item = page.get_images()[0]
            self.assertEqual(8, item[4])
            source = doc.extract_image(item[0])['image']
            raw = ImagesExtractor(page).extract_images()[0]
        self.assertEqual(source, raw['image'])

    def test_indexed_one_bit_pdf_keeps_two_exact_colors_in_png(self):
        image = Image.frombytes('1', (1024, 768), random.Random(25).randbytes(128 * 768))
        doc, page = page_with_gray_image(image, bits_per_component=1)
        with doc:
            xref = page.get_images()[0][0]
            # Include adjacent palette values to catch accidental color quantization.
            doc.xref_set_key(xref, 'ColorSpace', '[/Indexed /DeviceRGB 1 <102030102031>]')
            expanded = doc.extract_image(xref)['image']
            raw = ImagesExtractor(page).extract_images()[0]
        before, after = Image.open(io.BytesIO(expanded)), Image.open(io.BytesIO(raw['image']))
        self.assertEqual('PNG', after.format)
        self.assertEqual('P', after.mode)
        self.assertEqual(1, raw['image'][24])  # IHDR bit depth
        self.assertEqual(before.size, after.size)
        self.assertEqual(before.convert('RGB').tobytes(), after.convert('RGB').tobytes())
        self.assertLess(len(raw['image']), len(expanded))

    def test_inverted_binary_pdf_keeps_decoded_pixel_values(self):
        image = Image.frombytes('1', (1024, 768), random.Random(26).randbytes(128 * 768))
        doc, page = page_with_gray_image(image, bits_per_component=1)
        with doc:
            xref = page.get_images()[0][0]
            doc.xref_set_key(xref, 'Decode', '[1 0]')
            expected = fitz.Pixmap(doc, xref).samples
            raw = ImagesExtractor(page).extract_images()[0]
        restored = Image.open(io.BytesIO(raw['image']))
        self.assertEqual(expected, restored.convert('L').tobytes())
        self.assertEqual(image.size, restored.size)

    def test_bilevel_recovery_never_quantizes_gray_or_transparency(self):
        with fitz.open() as doc:
            page = doc.new_page()
            extractor = ImagesExtractor(page)
            for value, transparency in ((128, None), (0, 0)):
                with self.subTest(value=value, transparency=transparency):
                    stream = io.BytesIO()
                    options = {} if transparency is None else {'transparency': transparency}
                    Image.new('L', (100, 80), value).save(stream, 'PNG', **options)
                    raw = {'image': stream.getvalue()}
                    self.assertIs(raw, extractor._restore_bilevel_png_depth(raw, 1))

    def test_rgb_image_with_three_colors_is_never_reduced_to_two(self):
        image = Image.new('RGB', (100, 80), (0, 0, 0))
        image.putpixel((1, 1), (255, 255, 255))
        image.putpixel((2, 2), (255, 0, 0))
        stream = io.BytesIO()
        image.save(stream, 'PNG')
        raw = {'image': stream.getvalue()}
        with fitz.open() as doc:
            page = doc.new_page()
            self.assertIs(raw, ImagesExtractor(page)._restore_bilevel_png_depth(raw, 1))

    def test_binary_pdf_scan_respects_explicit_jpeg_policy(self):
        stream = io.BytesIO()
        Image.new('1', (640, 480), 1).save(stream, 'PNG')
        doc, page = page_with_image(stream.getvalue())
        with doc:
            raw = ImagesExtractor(page, ImageSettings(image_format='jpeg')).extract_images()[0]
        image = Image.open(io.BytesIO(raw['image']))
        self.assertEqual('JPEG', image.format)
        self.assertEqual((640, 480), image.size)

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

    def test_image_rotation_keeps_jpeg_bytes_and_native_dimensions(self):
        data = encoded_image()
        doc, page = page_with_image(data, rotate=90)
        with doc:
            raw = ImagesExtractor(page).extract_images()[0]
        self.assertEqual('JPEG', Image.open(io.BytesIO(raw['image'])).format)
        self.assertEqual((640, 480), (raw['width'], raw['height']))
        self.assertEqual(270, raw['rotation'])
        self.assertEqual(data, raw['image'])

    def test_default_composition_uses_native_density_without_upscaling(self):
        doc, page = page_with_image(encoded_image())
        with doc:
            page.insert_image(fitz.Rect(100, 100, 300, 250), stream=encoded_image())
            raw = ImagesExtractor(page).extract_images()[0]
        self.assertEqual((800, 640), (raw['width'], raw['height']))

    def test_stencil_composition_keeps_native_pixels(self):
        with fitz.open() as doc:
            page = doc.new_page(width=400, height=400)
            image_xref = doc.get_new_xref()
            doc.update_object(image_xref, '<< /Type /XObject /Subtype /Image /Width 300 /Height 600 /ImageMask true /BitsPerComponent 1 >>')
            doc.update_stream(image_xref, b'\x55' * (38 * 600))
            resource_xref = doc.get_new_xref()
            doc.update_object(resource_xref, f'<< /XObject << /MaskImage {image_xref} 0 R >> >>')
            doc.xref_set_key(page.xref, 'Resources', f'{resource_xref} 0 R')
            stream_xref = doc.get_new_xref()
            doc.update_object(stream_xref, '<< >>')
            doc.update_stream(stream_xref, b'q 0 0 1 rg 100 0 0 200 30 50 cm /MaskImage Do Q')
            doc.xref_set_key(page.xref, 'Contents', f'{stream_xref} 0 R')
            raw = ImagesExtractor(page).extract_images()[0]
            self.assertEqual((300, 600), (raw['width'], raw['height']))
            limited = ImagesExtractor(page, ImageSettings(image_max_dpi=144)).extract_images()[0]
            self.assertEqual((200, 400), (limited['width'], limited['height']))

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
            raw = ImagesExtractor(page, ImageSettings(image_format='jpeg', image_jpeg_quality=100)).extract_images()[0]
        image = Image.open(io.BytesIO(raw['image']))
        self.assertEqual('RGBA', image.mode)
        self.assertEqual((640, 480), image.size)
        self.assertEqual(270, raw['rotation'])
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

    def test_page_rotation_preserves_jpeg_bytes_and_drawingml_transform(self):
        from xml.etree import ElementTree as ET
        data = encoded_image(size=(641, 479))  # Not MCU-aligned: no cropping is acceptable.
        with tempfile.TemporaryDirectory() as tmp:
            pdf, output = Path(tmp) / 'rotated.pdf', Path(tmp) / 'rotated.docx'
            with fitz.open() as doc:
                for rotation in (90, 180, 270):
                    page = doc.new_page(width=400, height=400)
                    page.insert_image(fitz.Rect(50, 50, 250, 200), stream=data)
                    page.set_rotation(rotation)
                    raw = ImagesExtractor(page).extract_images()[0]
                    self.assertEqual(data, raw['image'])
                    self.assertEqual(rotation, raw['rotation'])
                doc.save(pdf)
            converter = Converter(str(pdf))
            try:
                converter.convert(str(output), ignore_page_error=False)
            finally:
                converter.close()
            with zipfile.ZipFile(output) as archive:
                media = [archive.read(name) for name in archive.namelist() if name.startswith('word/media/')]
                self.assertEqual([data], media)
                xml = ET.fromstring(archive.read('word/document.xml'))
            ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
                  'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
                  'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}
            transforms = xml.findall('.//pic:spPr/a:xfrm', ns)
            self.assertEqual([90*60000, 180*60000, 270*60000], [int(t.get('rot')) for t in transforms])
            drawings = xml.findall('.//wp:anchor', ns)
            self.assertEqual(3, len(drawings))
            for drawing in drawings:
                extent = drawing.find('wp:extent', ns)
                pic_extent = drawing.find('.//pic:spPr/a:xfrm/a:ext', ns)
                self.assertEqual((extent.get('cx'), extent.get('cy')),
                                 (pic_extent.get('cx'), pic_extent.get('cy')))

    def test_float_picture_rotation_preserves_original_stream(self):
        from docx import Document
        from pdf2docx.common.docx import add_float_image
        data = encoded_image()
        document = Document()
        add_float_image(document.add_paragraph(), io.BytesIO(data), 150, 20, 30, height=200, rotation=90)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'float.docx'
            document.save(path)
            with zipfile.ZipFile(path) as archive:
                media = [archive.read(name) for name in archive.namelist() if name.startswith('word/media/')]
                self.assertEqual([data], media)
                self.assertIn(b'rot="5400000"', archive.read('word/document.xml'))

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
