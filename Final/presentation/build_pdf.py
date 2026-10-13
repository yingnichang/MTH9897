"""Build the final PDF slides from the same data-driven content as build_deck.py.

Run: python presentation/build_pdf.py
Requires python-pptx, reportlab and Pillow. Text and tables remain searchable.
"""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from build_deck import build

EMU = 12700
FONT, BOLD = 'Helvetica', 'Helvetica-Bold'
font_dir = Path('C:/Windows/Fonts')
if (font_dir / 'arial.ttf').exists():
    pdfmetrics.registerFont(TTFont('SlideArial', str(font_dir / 'arial.ttf')))
    pdfmetrics.registerFont(TTFont('SlideArialBold', str(font_dir / 'arialbd.ttf')))
    FONT, BOLD = 'SlideArial', 'SlideArialBold'
else:
    import matplotlib
    font_dir = Path(matplotlib.get_data_path()) / 'fonts/ttf'
    pdfmetrics.registerFont(TTFont('SlideSans', str(font_dir / 'DejaVuSans.ttf')))
    pdfmetrics.registerFont(TTFont('SlideSansBold', str(font_dir / 'DejaVuSans-Bold.ttf')))
    FONT, BOLD = 'SlideSans', 'SlideSansBold'


def paragraph(pdf, text, x, top, width, size, bold=False, color=black):
    style = ParagraphStyle('slide', fontName=BOLD if bold else FONT,
                           fontSize=size, leading=size * 1.2, textColor=color)
    p = Paragraph(escape(text).replace('\n', '<br/>'), style)
    _, height = p.wrap(width, 10000)
    p.drawOn(pdf, x, top - height)
    return height


def export(source, destination):
    deck = Presentation(source)
    width, height = deck.slide_width / EMU, deck.slide_height / EMU
    pdf = canvas.Canvas(str(destination), pagesize=(width, height))
    pdf.setTitle('The Conservative Formula: CRSP Replication, 1929–2024')
    pdf.setAuthor('Yingni Chang')
    for slide in deck.slides:
        pdf.setFillColor(white)
        pdf.rect(0, 0, width, height, fill=1, stroke=0)
        for shape in slide.shapes:
            x, y, w, h = shape.left/EMU, shape.top/EMU, shape.width/EMU, shape.height/EMU
            if x < 0 or y < 0 or x+w > width+1 or y+h > height+1:
                raise ValueError('Slide object extends beyond the page boundary')
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                pdf.drawImage(ImageReader(BytesIO(shape.image.blob)), x, height-y-h, w, h, mask='auto')
            elif shape.has_table:
                table = shape.table
                top = height-y
                for row_idx, row in enumerate(table.rows):
                    rh = row.height/EMU
                    # Expand rows to fit wrapped text instead of clipping it.
                    for col_idx, cell in enumerate(row.cells):
                        cw = table.columns[col_idx].width/EMU
                        font = cell.text_frame.paragraphs[0].font
                        size = font.size.pt if font.size else 11
                        style = ParagraphStyle('measure', fontName=BOLD if row_idx == 0 else FONT,
                                               fontSize=size, leading=size*1.2)
                        _, needed = Paragraph(escape(cell.text), style).wrap(cw-10, 10000)
                        rh = max(rh, needed+9)
                    if top-rh < 18:
                        raise ValueError('Table exceeds slide: split it across slides')
                    left = x
                    for col_idx, cell in enumerate(row.cells):
                        cw = table.columns[col_idx].width/EMU
                        pdf.setStrokeColor(black)
                        pdf.setLineWidth(0.4)
                        pdf.rect(left, top-rh, cw, rh, stroke=1, fill=0)
                        font = cell.text_frame.paragraphs[0].font
                        size = font.size.pt if font.size else 11
                        used = paragraph(pdf, cell.text, left+5, top-4, cw-10, size, row_idx == 0)
                        if used > rh-7:
                            raise ValueError(f'Table text exceeds row height: {cell.text[:60]}')
                        left += cw
                    top -= rh
            elif shape.has_text_frame:
                tf = shape.text_frame
                top = height-y-tf.margin_top/EMU
                for para in tf.paragraphs:
                    size = para.font.size.pt if para.font.size else 15
                    rgb = None
                    try: rgb = para.font.color.rgb
                    except (AttributeError, TypeError): pass
                    color = HexColor('#'+str(rgb)) if rgb else HexColor('#1f2a33')
                    used = paragraph(pdf, para.text, x+tf.margin_left/EMU, top,
                                     w-(tf.margin_left+tf.margin_right)/EMU,
                                     size, bool(para.font.bold), color)
                    top -= used + (para.space_after.pt if para.space_after else 0)
                    if top < height-y-h-2:
                        raise ValueError(f'Text exceeds slide textbox: {para.text[:60]}')
        pdf.showPage()
    pdf.save()
    return destination


if __name__ == '__main__':
    source = build()
    output = export(source, Path(__file__).resolve().parent / 'conservative_formula.pdf')
    print(f'Wrote {output}')
