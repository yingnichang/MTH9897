"""Build the final PDF slides from the same data-driven content as build_deck.py.

Project authors: Yingni Chang and Yikai Shen.

Run: python presentation/build_pdf.py
Requires python-pptx, reportlab and Pillow. Text and tables remain searchable.
"""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from xml.sax.saxutils import escape

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research import results
from research.feedback_summary import extras
from numeric_views import make_views

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


INK, MUTED = HexColor('#203449'), HexColor('#526475')
HEADER, RULE, STRIPE = HexColor('#203449'), HexColor('#D7E0E7'), HexColor('#F1F5F8')


def paragraph(pdf, text, x, top, width, size, bold=False, color=INK, align=0, measure=False):
    style = ParagraphStyle('slide', fontName=BOLD if bold else FONT,
                           fontSize=size, leading=size * 1.28, textColor=color,
                           alignment=align, splitLongWords=False)
    p = Paragraph(escape(text).replace('\n', '<br/>'), style)
    _, height = p.wrap(width, 10000)
    if not measure:
        p.drawOn(pdf, x, top - height)
    return height


def body_height(paras, width, size, gap):
    return sum(paragraph(None, p.text, 0, 0, width-(18 if p.level else 0),
                         size-(2 if p.level else 0), measure=True)
               for p in paras) + gap * max(0, len(paras)-1)


def fit_body(paras, width, height, preferred, minimum=16):
    for half in range(round(preferred*2), round(minimum*2)-1, -1):
        size = half/2
        gap = max(8, size*.48)
        used = body_height(paras, width, size, gap)
        if used <= height:
            return size, gap, used
    raise ValueError('Slide body does not fit without changing content')


def draw_body(pdf, paras, x, top, width, size, gap):
    for i, p in enumerate(paras):
        indent = 18 if p.level else 0
        used = paragraph(pdf, p.text, x+indent, top, width-indent,
                         size-(2 if p.level else 0), color=MUTED if p.level else INK)
        top -= used + (gap if i+1 < len(paras) else 0)
    return top


def table_layout(table, width, size, fractions):
    widths = [width*f for f in fractions]
    cells = table if isinstance(table, list) else [[c.text for c in row.cells] for row in table.rows]
    heights = []
    for row_i, row in enumerate(cells):
        needed = max(paragraph(None, value, 0, 0, cw-18, size,
                               bold=row_i == 0 or col_i == 0, measure=True)
                     for col_i, (value, cw) in enumerate(zip(row, widths)))
        heights.append(max(size*2.05, needed+12))
    return widths, heights, cells


def fit_table(table, width, height, preferred, fractions):
    for half in range(round(preferred*2), 25, -1):
        size = half/2
        layout = table_layout(table, width, size, fractions)
        words_fit = all(pdfmetrics.stringWidth(word, BOLD if ri == 0 or ci == 0 else FONT, size)
                        <= layout[0][ci]-18
                        for ri, row in enumerate(layout[2]) for ci, value in enumerate(row)
                        for word in value.split())
        if words_fit and sum(layout[1]) <= height:
            return size, layout
    raise ValueError('Slide table does not fit without changing content')


def draw_table(pdf, x, top, size, layout, prose=False):
    widths, heights, cells = layout
    for row_i, (row, rh) in enumerate(zip(cells, heights)):
        pdf.setFillColor(HEADER if row_i == 0 else STRIPE if row_i % 2 else white)
        pdf.rect(x, top-rh, sum(widths), rh, stroke=0, fill=1)
        left = x
        for col_i, (value, cw) in enumerate(zip(row, widths)):
            align = 0 if col_i == 0 or prose else 1
            needed = paragraph(None, value, 0, 0, cw-18, size,
                               bold=row_i == 0 or col_i == 0, measure=True)
            paragraph(pdf, value, left+9, top-(rh-needed)/2, cw-18, size,
                      bold=row_i == 0 or col_i == 0,
                      color=white if row_i == 0 else INK, align=align)
            left += cw
        pdf.setStrokeColor(RULE)
        pdf.setLineWidth(.6)
        pdf.line(x, top-rh, x+sum(widths), top-rh)
        top -= rh
    return top


def draw_picture(pdf, shape, x, top, width, height):
    ratio = shape.width/shape.height
    w = min(width, height*ratio)
    h = w/ratio
    pdf.drawImage(ImageReader(BytesIO(shape.image.blob)), x+(width-w)/2,
                  top-(height-h)/2-h, w, h, mask='auto')


def text_paras(lines):
    return [SimpleNamespace(text=line, level=0) for line in lines]


def draw_numeric_view(pdf, view, pictures, tables, x, top, width, height):
    """Place a verified numerical table with its context and source figure."""
    kind = view['kind']
    intro, notes = text_paras(view['intro']), text_paras(view['notes'])
    bottom = top-height
    if kind == 'wide':
        intro_h = body_height(intro, width, 16, 6)
        notes_h = body_height(notes, width, 16, 6)
        gaps = (12 if intro else 0)+(12 if notes else 0)
        size, layout = fit_table(view['rows'], width, height-intro_h-notes_h-gaps,
                                 view['font'], view['widths'])
        if intro:
            draw_body(pdf, intro, x, top, width, 16, 6)
        table_top = top-intro_h-(12 if intro else 0)
        draw_table(pdf, x, table_top, size, layout, prose=view['prose'])
        if notes:
            draw_body(pdf, notes, x, bottom+notes_h, width, 16, 6)
        return

    left_w = width*.49
    right_x, right_w = x+left_w+28, width-left_w-28
    if kind == 'with_bottom_table':
        base_size, base_layout = fit_table(tables[0], width, 190, 14, [.20]+[.80/6]*6)
        base_h = sum(base_layout[1])
        notes_h = body_height(notes, width, 13.5, 6)
        main_h = height-base_h-notes_h-24
        size, layout = fit_table(view['rows'], left_w, main_h,
                                 view['font'], view['widths'])
        draw_table(pdf, x, top, size, layout)
        draw_body(pdf, notes, x, bottom+base_h+12+notes_h, width, 13.5, 6)
        draw_picture(pdf, pictures[0], right_x, top, right_w, main_h)
        draw_table(pdf, x, bottom+base_h, base_size, base_layout)
        return

    if kind == 'picture_with_notes_below':
        intro_h = body_height(intro, width, 15, 6)
        notes_h = body_height(notes, width, 15, 6)
        main_h = height-intro_h-notes_h-24
        size, layout = fit_table(view['rows'], left_w, main_h,
                                 view['font'], view['widths'])
        draw_body(pdf, intro, x, top, width, 15, 6)
        main_top = top-intro_h-12
        draw_table(pdf, x, main_top, size, layout)
        draw_picture(pdf, pictures[0], right_x, main_top, right_w, main_h)
        draw_body(pdf, notes, x, bottom+notes_h, width, 15, 6)
        return

    intro_h = body_height(intro, left_w, 16, 6)
    notes_h = body_height(notes, left_w, 14.5, 6)
    gaps = (12 if intro else 0)+(12 if notes else 0)
    size, layout = fit_table(view['rows'], left_w, height-intro_h-notes_h-gaps,
                             view['font'], view['widths'])
    if intro:
        draw_body(pdf, intro, x, top, left_w, 16, 6)
    draw_table(pdf, x, top-intro_h-(12 if intro else 0), size, layout)
    if notes:
        draw_body(pdf, notes, x, bottom+notes_h, left_w, 14.5, 6)
    if kind == 'with_picture':
        draw_picture(pdf, pictures[0], right_x, top, right_w, height)
    elif kind == 'with_side_table':
        rows = [[c.text for c in row.cells] for row in tables[0].rows]
        rows[0] = ['Period', 'Carhart alpha', 'Excess return']
        paragraph(pdf, 'Break-even cost (bps per dollar traded)', right_x, top, right_w, 16, bold=True)
        size_r, layout_r = fit_table(rows, right_w, height-48, 16, [.38, .30, .32])
        draw_table(pdf, right_x, top-45, size_r, layout_r)
    else:
        raise ValueError(f'Unknown numerical layout: {kind}')


def draw_feedback_slide(pdf, view, width, height, root):
    margin=42; available_width=width-2*margin
    title_h=paragraph(pdf, view['title'], margin, height-30, available_width, 32, bold=True)
    top=min(height-116,height-30-title_h-26)
    notes=text_paras([view.get('notes','')]); nh=body_height(notes,available_width,14.5,6)
    bottom=48+nh+15
    if 'figure' in view:
        path=results.path(*view['figure'],root=root)
        from PIL import Image
        with Image.open(path) as im: iw,ih=im.size
        shape=SimpleNamespace(width=iw,height=ih,image=SimpleNamespace(blob=path.read_bytes()))
        draw_picture(pdf,shape,margin,top,available_width,top-bottom)
    else:
        intro=text_paras([view['intro']]) if view.get('intro') else []
        ih=body_height(intro,available_width,16,6) if intro else 0
        if intro:draw_body(pdf,intro,margin,top,available_width,16,6)
        size,layout=fit_table(view['rows'],available_width,top-bottom-ih-12,17,view['widths'])
        draw_table(pdf,margin,top-ih-(12 if intro else 0),size,layout,prose=view.get('prose',False))
    draw_body(pdf,notes,margin,48+nh,available_width,14.5,6)
    paragraph(pdf,'Yingni Chang and Yikai Shen | MTH 9897',margin,26,available_width,9,color=MUTED)
    pdf.showPage()


def export(source, destination, root=None):
    """Build readable PDF evidence tables from the same saved numerical results.

    The PPTX is read only. Five feedback slides follow the original 17 content slides. Existing figures, dimensions and scientific
    results are retained; numerical prose is reorganized into labeled tables.
    """
    deck = Presentation(source)
    width, height = deck.slide_width / EMU, deck.slide_height / EMU
    pdf = canvas.Canvas(str(destination), pagesize=(width, height))
    pdf.setTitle('The Conservative Formula: CRSP Replication, 1929–2024')
    pdf.setAuthor('Yingni Chang and Yikai Shen')
    root = results.RESULTS if root is None else root
    views = make_views(root)
    margin, gutter = 42, 28
    content_width = width-2*margin
    bottom = 48
    fractions = {4: [.36, .64], 6: [.20]+[.80/6]*6,
                 8: [.40, .25, .35], 9: [.17, .09, .20, .27, .27],
                 15: [.25, .19, .23, .15, .18]}
    for number, slide in enumerate(deck.slides, 1):
        if number == 18:
            for view in extras(root):
                draw_feedback_slide(pdf, view, width, height, root)
            break  # The old professor-questions slide is excluded from the final submission.
        pdf.setFillColor(white)
        pdf.rect(0, 0, width, height, fill=1, stroke=0)
        text_shapes = [s for s in slide.shapes if s.has_text_frame]
        if len(text_shapes) != 3:
            raise ValueError('Expected title, body and author credit on each slide')
        title, body, footer = [s.text_frame for s in text_shapes]
        pictures = [s for s in slide.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
        tables = [s.table for s in slide.shapes if s.has_table]
        if len(pictures) > 1 or len(tables) > 1:
            raise ValueError('Unexpected slide evidence layout')
        title_size = 38 if number == 1 else 32
        title_top = height-(55 if number == 1 else 30)
        slide_title = title.paragraphs[0].text
        used = paragraph(pdf, slide_title, margin, title_top,
                         content_width, title_size, bold=True)
        if len(title.paragraphs) > 1:
            used += 9
            for p in list(title.paragraphs)[1:]:
                used += paragraph(pdf, p.text, margin, title_top-used,
                                  content_width, 15, color=MUTED)
        body_top = min(height-(190 if number == 1 else 116), title_top-used-26)
        available = body_top-bottom
        paras = list(body.paragraphs)
        if number in views:
            draw_numeric_view(pdf, views[number], pictures, tables, margin,
                              body_top, content_width, available)
        elif not pictures and not tables:
            size, gap, used = fit_body(paras, content_width, available, 24)
            draw_body(pdf, paras, margin, body_top-(available-used)*.18,
                      content_width, size, gap)
        elif pictures and tables and number == 9:
            # Keep the rolling chart tall beside the period table and its explanation.
            left_w = content_width*.56
            size_t, layout = fit_table(tables[0], left_w, available*.60, 14,
                                       [.19, .14, .17, .25, .25])
            table_h = sum(layout[1])
            size, gap, used = fit_body(paras, left_w, available-table_h-22, 21)
            draw_body(pdf, paras, margin, body_top, left_w, size, gap)
            draw_picture(pdf, pictures[0], margin+left_w+gutter, body_top,
                         content_width-left_w-gutter, available)
            draw_table(pdf, margin, bottom+table_h, size_t, layout)
        elif pictures and tables:
            # Preserve a wide table below the text/chart comparison.
            table = tables[0]
            size_t, layout = fit_table(table, content_width, 190, 14,
                                       fractions[number])
            table_h = sum(layout[1])
            main_h = available-table_h-20
            left_w = content_width*.49
            size, gap, used = fit_body(paras, left_w, main_h, 21)
            draw_body(pdf, paras, margin, body_top, left_w, size, gap)
            draw_picture(pdf, pictures[0], margin+left_w+gutter, body_top,
                         content_width-left_w-gutter, main_h)
            draw_table(pdf, margin, bottom+table_h, size_t, layout)
        else:
            # Use a balanced text/evidence spread instead of small objects at the top.
            left_w = content_width*(.49 if tables else .46)
            right_w = content_width-left_w-gutter
            size, gap, used = fit_body(paras, left_w, available, 21)
            draw_body(pdf, paras, margin, body_top, left_w, size, gap)
            if pictures:
                draw_picture(pdf, pictures[0], margin+left_w+gutter, body_top,
                             right_w, available)
            else:
                size_t, layout = fit_table(tables[0], right_w, available, 17,
                                           fractions[number])
                table_h = sum(layout[1])
                draw_table(pdf, margin+left_w+gutter, body_top-(available-table_h)*.15,
                           size_t, layout, prose=number == 4)
        paragraph(pdf, footer.text, margin, 26, content_width, 9, color=MUTED)
        pdf.showPage()
    pdf.save()
    return destination


if __name__ == '__main__':
    source = Path(__file__).resolve().parent / 'conservative_formula.pptx'  # read-only layout input
    output = export(source, Path(__file__).resolve().parent / 'conservative_formula.pdf')
    print(f'Wrote {output}')
