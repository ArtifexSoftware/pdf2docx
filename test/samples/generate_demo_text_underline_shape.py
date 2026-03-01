"""Generate a minimal PDF sample for non-hyperlink underline strip handling.

This sample creates a normal text phrase with a decorative underline strip and
adds a non-iso curve nearby so path extraction may convert the strip into an
inline image block.
"""

import fitz


def build(out_path: str) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    text = "Normal underlined text demo (not hyperlink)."
    page.insert_text(
        fitz.Point(80, 300),
        text,
        fontsize=18,
        fontname="helv",
        color=(0, 0, 0),
    )

    rect = page.search_for("underlined text demo")[0]

    # Decorative underline strip.
    underline = fitz.Rect(rect.x0, rect.y1 - 1.8, rect.x1, rect.y1 + 0.6)
    page.draw_rect(underline, color=None, fill=(0, 0, 0), width=0)

    # Non-iso path near baseline to force vector-region image clipping.
    y = rect.y1 - 0.8
    shape = page.new_shape()
    shape.draw_bezier(
        (rect.x0, y),
        (rect.x0 + 35, y - 1.0),
        (rect.x0 + 70, y + 1.0),
        (rect.x0 + 105, y),
    )
    shape.finish(color=(0, 0, 0), fill=None, width=0.4)
    shape.commit()

    doc.save(out_path)


if __name__ == "__main__":
    build("demo-text-underline-shape.pdf")
