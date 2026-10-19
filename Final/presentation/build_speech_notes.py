"""Create editable speaking notes and a rehearsal PDF from the saved slide results.

Project authors: Yingni Chang and Yikai Shen.
Run from Final: python presentation/build_speech_notes.py
"""
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape

FINAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FINAL))
from build_report_pdf import fonts, text
from research import results
from speech_notes import AUTHORS, make_notes, question_answers, word_count, write_markdown
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether

PDF = FINAL / "output/pdf/conservative_formula_speech_notes.pdf"
MARKDOWN = FINAL / "presentation/speaker_notes.md"


def build_pdf(notes, destination=PDF):
    fonts()
    ink, muted = colors.HexColor("#243746"), colors.HexColor("#526877")
    body = ParagraphStyle("SpeechBody", fontName="ReportSans", fontSize=10.5,
                          leading=14.7, textColor=ink, spaceAfter=7)
    title = ParagraphStyle("SpeechTitle", fontName="ReportSansBold", fontSize=15,
                           leading=19, textColor=ink, spaceAfter=8, keepWithNext=True)
    small = ParagraphStyle("SpeechCue", fontName="ReportSans", fontSize=8.6,
                           leading=11.5, textColor=muted, spaceAfter=8)
    story = []
    words = sum(word_count(n) for n in notes)
    story.append(Paragraph("Speech Notes for the Conservative Formula", title))
    story.append(Paragraph(escape(AUTHORS), body))
    story.append(Paragraph(f"Read-aloud script: approximately {words:,} words, or "
                           f"{words/130:.0f} minutes at 130 words per minute. Allow "
                           f"{math.floor(words/130)}-{math.ceil(words/130+2)} minutes with pauses. "
                           "Cues are reminders, not spoken lines. Optional split: Yingni, slides 1-9; "
                           "Yikai, slides 10-23.", small))
    for i,note in enumerate(notes):
        if i and i%2==0: story.append(PageBreak())
        story.append(Paragraph(f"Slide {note['number']} | {escape(note['title'])}", title))
        story.append(Paragraph("Cue: " + escape(note['cue']), small))
        for paragraph in note['paragraphs']:
            story.append(Paragraph(escape(text(paragraph)), body))
        if note['transition']:
            story.append(Paragraph("<b>Transition:</b> " + escape(text(note['transition'])), body))
        story.append(Spacer(1,10))
    story.append(PageBreak())
    story.append(Paragraph("Questions to Prepare For", title))
    for question,answer in question_answers():
        story.append(KeepTogether([Paragraph(escape(question), title),
                                  Paragraph(escape(text(answer)), body),Spacer(1,8)]))
    def footer(canvas,doc):
        canvas.saveState()
        canvas.setFont("ReportSans",8)
        canvas.setFillColor(muted)
        canvas.drawString(44, 23, AUTHORS + " | Presentation speech notes")
        canvas.drawRightString(letter[0]-44,23,str(doc.page))
        canvas.restoreState()
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    SimpleDocTemplate(str(destination),pagesize=letter,leftMargin=44,rightMargin=44,
                      topMargin=38,bottomMargin=40,author=AUTHORS,
                      title="Conservative Formula Presentation Speech Notes").build(
                          story,onFirstPage=footer,onLaterPages=footer)
    return destination


def main():
    notes = make_notes()
    assert len(notes)==23
    write_markdown(notes,MARKDOWN)
    pdf = build_pdf(notes)
    print(f"{len(notes)} slide scripts, {sum(word_count(n) for n in notes):,} spoken words.")
    print(f"Editable notes: {MARKDOWN}\nRehearsal PDF: {pdf}")


if __name__ == "__main__": main()
