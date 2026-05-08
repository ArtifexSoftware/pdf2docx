"""Generate a minimal PDF for hyperlink decorative inline-image strip regression.

This sample creates one hyperlink text and inserts a tiny blue strip image under
part of the hyperlink text. Older conversion may export that strip as an extra
inline drawing in DOCX.
"""

import base64
import fitz


PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAHAAAAAMCAIAAAA1Yq6mAAAAP0lEQVR4nO3WMREAMAzD"
    "QLv8qRaDS0Jb9QAy6Dyk2yLOAW/JoDwXCjMorMmlb37NhcIMCqt/KMuFwgwKM2hYDy0ZBv3P"
    "mMj1AAAAAElFTkSuQmCC"
)


def build(out_path: str) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    text = "Hyperlink image-strip demo: click here now."
    page.insert_text(
        fitz.Point(80, 700),
        text,
        fontsize=18,
        fontname="helv",
        color=(0, 0, 0),
    )

    rect = page.search_for("click here")[0]

    page.insert_link(
        {
            "kind": fitz.LINK_URI,
            "from": fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y1 + 2),
            "uri": "https://example.com/hyperlink-inline-strip",
        }
    )

    # Decorative blue strip inserted as an image under hyperlink text.
    strip = base64.b64decode(PNG_B64)
    image_bbox = fitz.Rect(rect.x0, rect.y1 - 2.5, rect.x1, rect.y1 + 0.5)
    page.insert_image(image_bbox, stream=strip)

    doc.save(out_path)


if __name__ == "__main__":
    build("demo-hyperlink-inline-image-strip.pdf")
