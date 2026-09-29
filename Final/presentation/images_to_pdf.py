"""Package high-resolution slide renders into a PDF, preserving the slide canvas."""
import json
import sys
from pathlib import Path
from reportlab.pdfgen import canvas
from pypdf import PdfReader

pages = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
output = Path(sys.argv[2])
output.parent.mkdir(parents=True, exist_ok=True)
pdf = canvas.Canvas(str(output), pagesize=(960, 540), pageCompression=1)
pdf.setTitle('Does the Conservative Formula Still Work?')
pdf.setSubject('MTH 9897 Project 8: first draft with synthetic demonstration results')
for image in pages:
    pdf.drawImage(image, 0, 0, width=960, height=540)
    pdf.showPage()
pdf.save()
reader = PdfReader(output)
assert len(reader.pages) == len(pages)
assert all(tuple(float(v) for v in p.mediabox[2:]) == (960, 540) for p in reader.pages)
print(f'Created {len(pages)} landscape PDF pages: {output}')
