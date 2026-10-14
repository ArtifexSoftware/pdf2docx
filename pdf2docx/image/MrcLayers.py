"""Keep JPEG backgrounds and binary stencil layers in simple scanned PDFs."""
from io import BytesIO
import math
import re

import fitz
from PIL import Image

from ..common.share import BlockType


# NUL is PDF whitespace too. Scanners often pad image-only content streams with
# it, including between an image name and Do; Python's bytes.isspace excludes it.
_WHITESPACE = b'\x00\t\n\f\r '
_TOKEN = re.compile(rb'[\x00\t\n\f\r ]+|%[^\r\n]*|/[^\x00\t\n\f\r ()<>{}\[\]/%]+|[-+]?(?:\d+\.\d*|\.\d+|\d+)|[A-Za-z]+')


def _image_paints(content):
    """Accept only simple image painting; complex graphics keep the renderer path."""
    operands, stack, paints = [], [], []
    color = (0, 0, 0)
    offset = 0
    while offset < len(content):
        token = _TOKEN.match(content, offset)
        if token is None:
            return None
        value = token.group()
        offset = token.end()
        if not value.strip(_WHITESPACE) or value.startswith(b'%'):
            continue
        if value.startswith(b'/'):
            try:
                operands.append(value[1:].decode('ascii'))
            except UnicodeDecodeError:
                return None
            continue
        try:
            number = float(value)
        except ValueError:
            number = None
        if number is not None:
            if not math.isfinite(number):
                return None
            operands.append(number)
            continue
        if value == b'q' and not operands:
            stack.append(color)
        elif value == b'Q' and not operands and stack:
            color = stack.pop()
        elif value == b'cm' and len(operands) == 6:
            if not all(isinstance(x, float) for x in operands):
                return None
            a, b, c, d, _, _ = operands
            if a <= 0 or d <= 0 or b != 0 or c != 0:
                return None
        elif value in (b'g', b'rg') and len(operands) == (1 if value == b'g' else 3):
            if not all(isinstance(x, float) and 0 <= x <= 1 for x in operands):
                return None
            components = operands * 3 if value == b'g' else operands
            color = tuple(round(x * 255) for x in components)
        elif value == b'Do' and len(operands) == 1 and isinstance(operands[0], str):
            paints.append((operands[0], color))
        else:
            return None
        operands = []
    return paints if paints and not stack and not operands else None


def extract_mrc_layers(page, settings):
    """Preserve a JPEG followed by colored binary stencils as ordered pictures.

    PDF CCITT stencil streams cannot be embedded directly in Word. A two-color
    indexed PNG retains their native pixels and paint color, with transparent
    background, without expanding the JPEG backdrop into a high-resolution PNG.
    Unsupported clipping, forms, transforms, and graphics states use rendering.
    """
    if page.get_xobjects() or page.first_annot is not None or page.first_widget is not None:
        return None
    items = page.get_images(full=True)
    if (len(items) < 2 or len({item[0] for item in items}) != len(items)
            or any(item[-1] != 0 for item in items)):
        return None
    paints = _image_paints(page.read_contents())
    resources = {item[7]: item for item in items}
    if (not paints or len(paints) != len(items)
            or {name for name, _ in paints} != set(resources)
            or len({name for name, _ in paints}) != len(paints)):
        return None
    doc = page.parent
    # Default color spaces and transparency groups can change the stencil paint.
    # Check inherited resources as well as the page's own graphics state.
    parent, visited = page.xref, set()
    while parent and parent not in visited:
        visited.add(parent)
        for key in ('Group', 'Resources/ColorSpace/DefaultGray',
                    'Resources/ColorSpace/DefaultRGB'):
            if doc.xref_get_key(parent, key)[0] != 'null':
                return None
        kind, value = doc.xref_get_key(parent, 'Parent')
        parent = int(value.split()[0]) if kind == 'xref' else 0
    if any(doc.xref_get_key(resources[name][0], 'ImageMask') != ('bool', 'true')
           for name, _ in paints[1:]):
        return None
    layers = []
    background_bbox = None
    for order, (name, color) in enumerate(paints):
        item = resources[name]
        xref = item[0]
        if item[1] or doc.xref_get_key(xref, 'Mask')[0] != 'null':
            return None
        occurrences = page.get_image_rects(item, transform=True)
        if len(occurrences) != 1:
            return None
        bbox, transform = occurrences[0]
        if (bbox.is_empty or bbox.is_infinite
                or transform.a <= 0 or transform.d <= 0
                or transform.b != 0 or transform.c != 0):
            return None
        stencil = doc.xref_get_key(xref, 'ImageMask') == ('bool', 'true')
        if order == 0:
            extracted = doc.extract_image(xref)
            if (stencil or not extracted or extracted['ext'] not in ('jpeg', 'jpg')
                    or extracted['colorspace'] not in (1, 3)
                    or doc.xref_get_key(xref, 'Decode')[0] != 'null'):
                return None
            image = extracted['image']
            background_bbox = bbox
            full_page = fitz.Rect(0, 0, page.cropbox.width, page.cropbox.height)
            # Scanner page dimensions can be rounded differently from the image
            # transform. Keep sub-point overscan at its original anchor position;
            # the page edge clips it without resampling or stretching any layer.
            if any(abs(a - b) > 1.0 for a, b in zip(bbox, full_page)):
                return None
        else:
            if (not stencil or item[4] != 1 or not page.cropbox.contains(bbox)
                    or not background_bbox.contains(bbox)):
                return None
            kind, decode = doc.xref_get_key(xref, 'Decode')
            if kind != 'null' and (kind != 'array' or decode not in ('[0 1]', '[1 0]')):
                return None
            mask = fitz.Pixmap(doc, xref)
            if mask.colorspace is not None or mask.n != 1 or not mask.alpha:
                return None
            indices = mask.samples.translate(bytes([0] + [1] * 255))
            png = Image.frombytes('P', (mask.width, mask.height), indices)
            # Keep RGB constant even under transparent pixels. Word/LibreOffice
            # can interpolate palette RGB and alpha separately when scaling;
            # transparent black would produce dark fringes on colored stencils.
            png.putpalette([*color, *color] + [0] * (256 * 3 - 6))
            output = BytesIO()
            png.save(output, 'PNG', bits=1, transparency=0,
                     compress_level=settings.image_png_compress_level)
            image = output.getvalue()
        raw = {'type': BlockType.IMAGE.value, 'bbox': tuple(bbox),
               'width': item[2], 'height': item[3], 'image': image, 'z_order': order}
        raw = settings.apply(raw, -page.rotation,
                             tuple(bbox * page.rotation_matrix))
        raw['mrc'] = {'group': page.number + 1, 'order': order, 'layers': len(paints),
                      'bounds': list(bbox), 'canvas': list(background_bbox),
                      'width': raw['width'], 'height': raw['height']}
        layers.append(raw)
    return layers
