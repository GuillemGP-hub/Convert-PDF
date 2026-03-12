import io
from typing import List, Tuple

from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.pdf import PageObject

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.pagesizes import letter


FONT_NAME = "Helvetica"
FONT_SIZE = 10


def _rect_to_xy(rect: List[float]) -> Tuple[float, float, float, float]:
    x1, y1, x2, y2 = [float(v) for v in rect]
    x = min(x1, x2)
    y = min(y1, y2)
    w = abs(x2 - x1)
    h = abs(y2 - y1)
    return x, y, w, h


def _draw_text_overlay(page_width: float, page_height: float, widgets: List[dict]) -> PdfReader:
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))

    c.setFont(FONT_NAME, FONT_SIZE)
    c.setFillGray(0)  # black

    for w in widgets:
        value = w["value"]
        if value in (None, "", "Off"):
            continue

        x, y, width, height = w["x"], w["y"], w["w"], w["h"]

        margin_x = 2
        baseline_y = y + (height - FONT_SIZE) / 2

        text = str(value)
        text_width = pdfmetrics.stringWidth(text, FONT_NAME, FONT_SIZE)

        align = w["align"]
        if align == "center":
            draw_x = x + (width - text_width) / 2
        elif align == "right":
            draw_x = x + width - text_width - margin_x
        else:
            draw_x = x + margin_x

        c.drawString(draw_x, baseline_y, text)

    c.showPage()
    c.save()
    packet.seek(0)
    return PdfReader(packet)


def flatten_pdf(input_path: str, output_path: str) -> None:
    reader = PdfReader(input_path)
    writer = PdfWriter()

    for page in reader.pages:
        widgets = []
        annots = page.get("/Annots")

        if annots:
            for a in annots:
                annot = a.get_object()
                if annot.get("/Subtype") == "/Widget":
                    rect = annot.get("/Rect")
                    x, y, w, h = _rect_to_xy(rect)

                    value = None
                    if "/V" in annot:
                        v = annot["/V"]
                        if hasattr(v, "get_object"):
                            v = v.get_object()
                        v = str(v)
                        if v == "On":
                            v = "✓"
                        value = v

                    q = annot.get("/Q")
                    align = {0: "left", 1: "center", 2: "right"}.get(q, "left")

                    widgets.append({
                        "x": x,
                        "y": y,
                        "w": w,
                        "h": h,
                        "value": value,
                        "align": align
                    })

        media_box = page.mediabox
        page_width = float(media_box.width)
        page_height = float(media_box.height)

        if widgets:
            overlay_pdf = _draw_text_overlay(page_width, page_height, widgets)
            overlay_page = overlay_pdf.pages[0]

            new_page = PageObject.create_blank_page(width=page_width, height=page_height)
            new_page.merge_page(page)
            new_page.merge_page(overlay_page)

            if "/Annots" in new_page:
                del new_page["/Annots"]

            writer.add_page(new_page)
        else:
            writer.add_page(page)

    if "/AcroForm" in reader.trailer["/Root"]:
        del reader.trailer["/Root"]["/AcroForm"]

    with open(output_path, "wb") as f:
        writer.write(f)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Flatten a filled PDF with form fields.")
    parser.add_argument("input", help="Input filled PDF")
    parser.add_argument("output", help="Output flattened PDF")
    args = parser.parse_args()

    flatten_pdf(args.input, args.output)
    print(f"PDF flattened and saved to: {args.output}")
