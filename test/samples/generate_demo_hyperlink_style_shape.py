"""Generate a minimal PDF sample for hyperlink style regressions.

This sample intentionally creates:
1) Two hyperlink annotations.
2) Blue decorative underlines drawn as vector paths.
3) A thin non-iso Bezier strip overlapping the links.

Older versions of pdf2docx may:
- emit malformed OOXML hyperlink structure,
- duplicate the decorative strip as an inline image (extra underline),
- miss hyperlink blue color from vector drawings.
"""

import fitz


def build(out_path: str) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    text = "[Demo links: click subscribe, click collect.]"
    page.insert_text(
        fitz.Point(80, 700),
        text,
        fontsize=18,
        fontname="helv",
        color=(0, 0, 0),
    )

    rect_sub = page.search_for("click subscribe")[0]
    rect_collect = page.search_for("click collect")[0]

    # Blue decorative underlines as separate vector fills.
    for rect in (rect_sub, rect_collect):
        underline = fitz.Rect(rect.x0, rect.y1 - 1.8, rect.x1, rect.y1 + 0.6)
        page.draw_rect(underline, color=None, fill=(0, 0, 0.93), width=0)

    # Long thin non-iso curve near the baseline to trigger shape->image path.
    y = rect_sub.y1 - 0.8
    shape = page.new_shape()
    shape.draw_bezier(
        (rect_sub.x0, y),
        (rect_sub.x0 + 60, y - 1.2),
        (rect_collect.x1 - 60, y + 1.2),
        (rect_collect.x1, y),
    )
    shape.finish(color=(0, 0, 0.93), fill=None, width=0.5)
    shape.commit()

    page.insert_link(
        {
            "kind": fitz.LINK_URI,
            "from": fitz.Rect(rect_sub.x0, rect_sub.y0, rect_sub.x1, rect_sub.y1 + 2),
            "uri": "https://example.com/sub",
        }
    )
    page.insert_link(
        {
            "kind": fitz.LINK_URI,
            "from": fitz.Rect(rect_collect.x0, rect_collect.y0, rect_collect.x1, rect_collect.y1 + 2),
            "uri": "https://example.com/collect",
        }
    )

    doc.save(out_path)


if __name__ == "__main__":
    build("demo-hyperlink-style-shape.pdf")
