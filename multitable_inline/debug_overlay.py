import fitz  # PyMuPDF

GREEN = (0, 1, 0)
BLUE = (0, 0, 1)
YELLOW = (1, 1, 0)  # 🔶 Drawing Number
RED = (1, 0, 0)  # 🔴 Title


def generate_debug_pdf(
    original_pdf,
    output_pdf,
    extracted_parts
):
    """
    Draws:
    - GREEN boxes → Part Numbers
    - BLUE boxes → Descriptions
    - YELLOW boxes → Drawing Numbers
    """

    doc = fitz.open(original_pdf)

    for part in extracted_parts:
        trace = part.get("trace")
        if not trace:
            continue

        page_index = part["page"] - 1
        page = doc[page_index]

        # ---- PN boxes (GREEN) ----
        for box in trace.get("pn_boxes", []):
            rect = fitz.Rect(
                box["x0"],
                box["top"],
                box["x1"],
                box["bottom"]
            )
            page.draw_rect(rect, color=GREEN, width=1.2)

        # ---- Description boxes (BLUE) ----
        for box in trace.get("desc_boxes", []):
            rect = fitz.Rect(
                box["x0"],
                box["top"],
                box["x1"],
                box["bottom"]
            )
            page.draw_rect(rect, color=BLUE, width=0.8)

        # ---- Drawing Number (YELLOW) ----
        drawing_box = trace.get("drawing_box")
        if drawing_box:
            rect = fitz.Rect(
                drawing_box["x0"],
                drawing_box["top"],
                drawing_box["x1"],
                drawing_box["bottom"]
            )
            page.draw_rect(rect, color=YELLOW, width=1.5)

        # ---- Title boxes (RED) ----
        for box in trace.get("title_boxes", []):
            rect = fitz.Rect(
                box["x0"],
                box["top"],
                box["x1"],
                box["bottom"]
            )
            page.draw_rect(rect, color=RED, width=1.8)

    doc.save(output_pdf)
    doc.close()
