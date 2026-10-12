# pdf2docx


![python-version](https://img.shields.io/badge/python->=3.6-green.svg)
![pypi-downloads](https://img.shields.io/pypi/dm/pdf2docx)

## ⚠️ Project Status

**pdf2docx is no longer actively maintained by Artifex.**

The repository will remain available and has been **relicensed under the MIT License** so that the community can freely use, fork, and maintain the project.

Pull requests from the community are welcome, but [Artifex](https://artifex.com) no longer provides active development or maintenance.

---

If you are looking for a **full-featured PDF processing library**, consider using [PyMuPDF](https://github.com/pymupdf/PyMuPDF) or [MuPDF.NET](https://github.com/ArtifexSoftware/MuPDF.NET).

## Documentation

- [Installation](https://pdf2docx.readthedocs.io/en/latest/installation.html)
- [Quickstart](https://pdf2docx.readthedocs.io/en/latest/quickstart.html)
    - [Convert PDF](https://pdf2docx.readthedocs.io/en/latest/quickstart.convert.html)
    - [Extract table](https://pdf2docx.readthedocs.io/en/latest/quickstart.table.html)
    - [Command Line Interface](https://pdf2docx.readthedocs.io/en/latest/quickstart.cli.html)
    - [Graphic User Interface](https://pdf2docx.readthedocs.io/en/latest/quickstart.gui.html)
- [Technical Documentation (In Chinese)](https://pdf2docx.readthedocs.io/en/latest/techdoc.html)
- [API Documentation](https://pdf2docx.readthedocs.io/en/latest/modules.html)

## Sample

![sample_compare.png](https://s1.ax1x.com/2020/08/04/aDryx1.png)

## RainLib image policy

This fork avoids inflating embedded JPEG images into PNG. Supported RGB/grayscale
JPEG and PNG streams without masks are reused at native resolution by default.
Rotations and downsampling retain the image format but require re-encoding.
Masks, overlapping images, unsupported encodings and vector graphics require
composition; these use PNG by default. Transparency is preserved even if JPEG
is requested. Images with PDF color transforms are decoded for correctness.

The default `clip_image_res_ratio` is **1.0 (72 DPI)** instead of 4.0. This controls
only page regions that must be rasterized, not the resolution of embedded images.
Increase it explicitly when fine vector graphics require more detail.

| CLI/API setting | Environment variable | Default | Behavior |
| --- | --- | --- | --- |
| `image_format` | `PDF2DOCX_IMAGE_FORMAT` | `preserve` | `preserve`, `jpeg`, `png` |
| `image_jpeg_quality` | `PDF2DOCX_IMAGE_JPEG_QUALITY` | `95` | Integer 1–100; used only when encoding JPEG |
| `image_max_dpi` | `PDF2DOCX_IMAGE_MAX_DPI` | `0` | 0 keeps native pixels; positive values only downsample |
| `image_png_compress_level` | `PDF2DOCX_IMAGE_PNG_COMPRESS_LEVEL` | `6` | Lossless PNG compression 0–9 when PNG is encoded |
| `clip_image_res_ratio` | `PDF2DOCX_CLIP_IMAGE_RES_RATIO` | `1.0` | Rasterization multiplier, 0.5–4.0 |

Explicit CLI/API settings override environment defaults. The legacy
`OFFICECLI_PDF_CLIP_IMAGE_RES_RATIO` is accepted as a fallback environment variable.
The Java service defaults to JPEG quality 100 with native pixel dimensions; standalone pdf2docx defaults to preserve and uses quality 95 when encoding is needed.

```bash
# Preserve original encoding and pixel dimensions where possible.
pdf2docx convert input.pdf output.docx

# Opt in to JPEG compression and a 150 DPI ceiling; alpha stays PNG.
pdf2docx convert input.pdf output.docx --image_format=jpeg --image_jpeg_quality=80 --image_max_dpi=150

# Lossless PNG encoding (may be larger than original JPEG).
pdf2docx convert input.pdf output.docx --image_format=png --image_png_compress_level=9

python3 -m unittest discover -s test -p test_image_policy.py -v
```

When `image_format=jpeg` and `image_jpeg_quality=100`, existing JPEG bytes are reused
if no rotation or downsampling is needed. PNG-to-JPEG conversion still requires
lossy JPEG encoding even at quality 100; alpha remains PNG.

New JPEG encodings at quality 100 use 4:4:4 chroma sampling (`subsampling=0`)
to avoid additional chroma downsampling. JPEG remains mathematically lossy and
maximum-quality JPEG can be larger than the source PNG; use preserve for lossless retention.
