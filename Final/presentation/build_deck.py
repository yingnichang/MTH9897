"""Compatibility entry point for the PDF presentation.

Authors: Yingni Chang and Yikai Shen.
The original PPTX supplies a read-only layout template. The deliverable is PDF.
Run from Final: python presentation/build_deck.py
"""
from pathlib import Path
from build_pdf import export
from speech_notes import make_notes, write_markdown
from research import results


def build(out_dir=None):
    folder=Path(__file__).resolve().parent if out_dir is None else Path(out_dir)
    folder.mkdir(parents=True,exist_ok=True)
    output=export(Path(__file__).resolve().parent/'conservative_formula.pptx',folder/'conservative_formula.pdf')
    write_markdown(make_notes(),folder/'speaker_notes.md')
    return output


if __name__=='__main__':print(build())
