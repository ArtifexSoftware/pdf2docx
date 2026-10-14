"""Layered scanner PDFs must not inflate their JPEG background into a full-page PNG."""
import io
import hashlib
import json
from pathlib import Path
import random
import tempfile
import unittest
import zipfile

import fitz
from PIL import Image
from lxml import etree

from pdf2docx import Converter
from pdf2docx.image.ImagesExtractor import ImagesExtractor
from pdf2docx.image.MrcLayers import _image_paints, extract_mrc_layers
from pdf2docx.image.ImageSettings import ImageSettings


def mrc_page(inverted=False, clipped=False, rotation=0, padding=b'', overscan=0):
    encoded = io.BytesIO()
    pixels = random.Random(43).randbytes(640 * 480)
    Image.frombytes('L', (640, 480), pixels).save(encoded, 'JPEG', quality=70)
    jpeg = encoded.getvalue()
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_image(page.rect, stream=jpeg)
    if overscan:
        name = page.get_images(full=True)[0][7]
        doc.update_stream(page.get_contents()[0],
                          f'q {400 + overscan} 0 0 {300 + overscan} 0 0 cm /{name} Do Q'.encode())
    mask = doc.get_new_xref()
    decode = '/Decode [1 0]' if inverted else ''
    doc.update_object(mask, '<< /Type /XObject /Subtype /Image /Width 1280 '
                      '/Height 960 /ImageMask true /BitsPerComponent 1 ' + decode + ' >>')
    doc.update_stream(mask, b'\x55' * (160 * 960))
    resources = int(doc.xref_get_key(page.xref, 'Resources')[1].split()[0])
    doc.xref_set_key(resources, 'XObject/Stencil', f'{mask} 0 R')
    stream = doc.get_new_xref()
    doc.update_object(stream, '<< >>')
    clip = b'0 0 100 100 re W n ' if clipped else b''
    doc.update_stream(stream, b'q ' + clip + b'0.22 g 400 0 0 300 0 0 cm /Stencil Do Q' + padding)
    content = page.get_contents() + [stream]
    doc.xref_set_key(page.xref, 'Contents', '[' + ' '.join(f'{x} 0 R' for x in content) + ']')
    page.set_rotation(rotation)
    return doc, page, jpeg, mask


class MrcLayersTest(unittest.TestCase):
    def test_pdf_null_whitespace_keeps_image_paints(self):
        self.assertEqual([('Background', (0, 0, 0)), ('Stencil', (56, 56, 56))],
                         _image_paints(b'q\x00400 0 0 300 0 0 cm /Background\x00Do Q'
                                       b'\x00\t\r\n\f 0.22 g q /Stencil Do Q\x00\x00'))
        # Unknown operators after padding must still select the renderer.
        self.assertIsNone(_image_paints(b'q /Background Do Q\x00BT ET'))

    def test_null_padded_content_retains_native_layers(self):
        doc, page, jpeg, _ = mrc_page(padding=b'\x00' * 745)
        with doc:
            layers = extract_mrc_layers(page, ImageSettings())
            self.assertIsNotNone(layers)
            self.assertEqual(2, len(layers))
            self.assertEqual(hashlib.sha256(jpeg).digest(),
                             hashlib.sha256(layers[0]['image']).digest())

    def test_subpoint_background_overscan_keeps_native_pixels_and_position(self):
        for padding in (b'', b'\x00' * 745):
            with self.subTest(padding=len(padding)):
                doc, page, jpeg, _ = mrc_page(padding=padding, overscan=0.68)
                with doc:
                    layers = extract_mrc_layers(page, ImageSettings())
                    self.assertIsNotNone(layers)
                    self.assertEqual(2, len(layers))
                    self.assertEqual(hashlib.sha256(jpeg).digest(),
                                     hashlib.sha256(layers[0]['image']).digest())
                    self.assertEqual((640, 480), (layers[0]['width'], layers[0]['height']))
                    self.assertAlmostEqual(-0.68, layers[0]['bbox'][1], places=3)
                    self.assertAlmostEqual(400.68, layers[0]['bbox'][2], places=3)
                    self.assertEqual(list(layers[0]['bbox']), layers[1]['mrc']['canvas'])

    def test_large_background_overscan_still_uses_composition(self):
        doc, page, _, _ = mrc_page(overscan=5)
        with doc:
            self.assertIsNone(extract_mrc_layers(page, ImageSettings()))

    def test_overscanned_stencil_still_uses_composition(self):
        doc, page, _, _ = mrc_page(overscan=0.68)
        with doc:
            doc.update_stream(page.get_contents()[-1],
                              b'q 0.22 g 400.5 0 0 300 0 0 cm /Stencil Do Q')
            self.assertIsNone(extract_mrc_layers(page, ImageSettings()))

    def test_preserves_native_jpeg_and_binary_stencil_pixels(self):
        doc, page, jpeg, mask = mrc_page()
        with doc:
            layers = ImagesExtractor(page).extract_images()
            self.assertEqual(2, len(layers))
            self.assertEqual(jpeg, layers[0]['image'])
            self.assertEqual((640, 480), (layers[0]['width'], layers[0]['height']))
            with Image.open(io.BytesIO(layers[1]['image'])) as png:
                self.assertEqual('P', png.mode)
                self.assertEqual((1280, 960), png.size)
                self.assertEqual(0, png.info['transparency'])
                rgba = png.convert('RGBA')
                self.assertEqual(fitz.Pixmap(doc, mask).samples,
                                 rgba.getchannel('A').tobytes())
                self.assertIn((56, 56, 56, 255), {color for _, color in rgba.getcolors(4)})
            self.assertEqual([0, 1], [layer['z_order'] for layer in layers])

    def test_inverted_stencil_decode_keeps_correct_transparency(self):
        doc, page, _, mask = mrc_page(inverted=True)
        with doc:
            layer = ImagesExtractor(page).extract_images()[1]
            with Image.open(io.BytesIO(layer['image'])) as png:
                self.assertEqual(fitz.Pixmap(doc, mask).samples,
                                 png.convert('RGBA').getchannel('A').tobytes())

    def test_colored_stencil_has_no_hidden_black_pixels_to_cause_scaling_halos(self):
        doc, page, _, mask = mrc_page()
        with doc:
            doc.update_stream(page.get_contents()[-1],
                              b'q 0.945 0.588 0.667 rg 400 0 0 300 0 0 cm /Stencil Do Q')
            layers = ImagesExtractor(page).extract_images()
            with Image.open(io.BytesIO(layers[1]['image'])) as png:
                self.assertEqual([241, 150, 170, 241, 150, 170], png.getpalette()[:6])
                self.assertEqual([(1280 * 960, (241, 150, 170))],
                                 png.convert('RGB').getcolors())
                self.assertEqual(hashlib.sha256(fitz.Pixmap(doc, mask).samples).digest(),
                                 hashlib.sha256(png.convert('RGBA').getchannel('A').tobytes()).digest())

    def test_clipped_stencils_keep_existing_composition(self):
        doc, page, _, _ = mrc_page(clipped=True)
        with doc:
            layers = ImagesExtractor(page).extract_images()
        self.assertEqual(1, len(layers))
        self.assertIsNone(layers[0].get('z_order'))

    def test_custom_gray_color_space_keeps_existing_composition(self):
        doc, page, _, _ = mrc_page()
        with doc:
            resources = int(doc.xref_get_key(page.xref, 'Resources')[1].split()[0])
            doc.xref_set_key(resources, 'ColorSpace',
                             '<< /DefaultGray [/CalGray << /WhitePoint [0.9505 1 1.0890] /Gamma 1.8 >>] >>')
            layers = ImagesExtractor(page).extract_images()
        self.assertEqual(1, len(layers))
        self.assertIsNone(layers[0].get('z_order'))

    def test_docx_contains_ordered_native_layers_without_size_expansion(self):
        self._check_docx(0)

    def test_rotated_mrc_page_keeps_native_media_and_layer_order(self):
        self._check_docx(90)

    def test_padded_overscanned_pages_keep_native_docx_layers_at_all_rotations(self):
        for rotation in (0, 90, 180, 270):
            with self.subTest(rotation=rotation):
                self._check_docx(rotation, padding=b'\x00' * 745, overscan=0.68)

    def test_identical_pages_keep_independently_replaceable_media(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = Path(folder) / 'repeated.pdf'
            doc, _, jpeg, _ = mrc_page()
            with doc:
                doc.fullcopy_page(0)
                doc.save(pdf)
            converter = Converter(str(pdf))
            try:
                converter.convert(str(pdf.with_suffix('.docx')), image_format='preserve')
            finally:
                converter.close()
            with zipfile.ZipFile(pdf.with_suffix('.docx')) as archive:
                images = [archive.read(n) for n in archive.namelist() if n.startswith('word/media/')]
                self.assertEqual(4, len(images))
                self.assertEqual(2, images.count(jpeg))

    def _check_docx(self, rotation, **fixture_settings):
        with tempfile.TemporaryDirectory() as folder:
            pdf = Path(folder) / 'mrc.pdf'
            output = pdf.with_suffix('.docx')
            doc, _, jpeg, _ = mrc_page(rotation=rotation, **fixture_settings)
            with doc:
                doc.save(pdf)
            converter = Converter(str(pdf))
            try:
                converter.convert(str(output), image_format='preserve', image_max_dpi=0)
            finally:
                converter.close()
            with zipfile.ZipFile(output) as archive:
                media = [archive.read(name) for name in archive.namelist()
                         if name.startswith('word/media/')]
                self.assertEqual(2, len(media))
                self.assertIn(jpeg, media)
                root = etree.fromstring(archive.read('word/document.xml'))
                namespaces = {'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
                              'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
                anchors = root.findall('.//wp:anchor', namespaces)
                self.assertEqual([0, 1], [int(a.get('relativeHeight')) for a in anchors])
                for order, anchor in enumerate(anchors):
                    description = anchor.find('wp:docPr', namespaces).get('descr')
                    metadata = json.loads(description.removeprefix('pdf2docx:mrc-v1:'))
                    self.assertEqual((1, order, 2), (metadata['group'], metadata['order'], metadata['layers']))
                if rotation:
                    for anchor in anchors:
                        self.assertEqual(str(rotation * 60000),
                                         anchor.find('.//a:xfrm', namespaces).get('rot'))
            self.assertLess(output.stat().st_size, pdf.stat().st_size * 1.5)
