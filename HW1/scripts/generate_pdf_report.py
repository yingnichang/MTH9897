"""Rebuild the standalone PDF report from the executed assignment notebook."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    ROOT / "scripts" / "report" / "extract_report_data.py",
    ROOT / "scripts" / "report" / "build_report.py",
]


def main():
    for step in STEPS:
        print(f"Running {step.relative_to(ROOT)}")
        subprocess.run([sys.executable, str(step)], cwd=ROOT, check=True)
    print(f"Report written to {ROOT / 'output' / 'pdf' / 'MTH9897_Bond_Relative_Value_Report.pdf'}")


if __name__ == "__main__":
    main()
