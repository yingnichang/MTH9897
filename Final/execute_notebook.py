"""Execute and validate the draft using the active Python environment.

Demo mode (default) executes the tracked notebook in place. With CF_MODE=crsp the executed copy is
written to output/crsp_run_<end year>.ipynb (git-ignored, as it may show licensed data) and the
tracked notebook is left as the demo run. CF_NB_OUT overrides the output path and CF_CELL_TIMEOUT
the per-cell timeout in seconds.
"""
import os
import sys
import json
import time
from pathlib import Path
import nbformat
from nbclient import NotebookClient

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))
from crsp_pipeline import config  # noqa: E402

mode = os.environ.get("CF_MODE", "demo")
if mode not in {"demo", "crsp"}:
    raise SystemExit(f"CF_MODE must be demo or crsp, got {mode!r}")
kernel_dir = root / ".jupyter" / "kernels" / "project-python"
kernel_dir.mkdir(parents=True, exist_ok=True)
(kernel_dir / "kernel.json").write_text(json.dumps({
    "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
    "display_name": "Project Python", "language": "python"
}), encoding="utf-8")
os.environ["JUPYTER_PATH"] = str(root / ".jupyter")
os.environ["JUPYTER_RUNTIME_DIR"] = str(root / ".jupyter" / "runtime")
os.environ["IPYTHONDIR"] = str(root / ".ipython")
os.environ["MPLCONFIGDIR"] = str(root / ".matplotlib")
path = root / "conservative_formula_first_draft.ipynb"
default_out = path if mode == "demo" else (
    root / "output" / f"crsp_run_{os.environ.get('CF_END', config.PAPER_END)[:4]}.ipynb")
out = Path(os.environ.get("CF_NB_OUT", default_out)).resolve()
if mode == "crsp" and out == path.resolve():
    raise SystemExit("A CRSP run must not overwrite the tracked demo notebook; set CF_NB_OUT elsewhere")
timeout = int(os.environ.get("CF_CELL_TIMEOUT", 300 if mode == "demo" else 3600))

nb = nbformat.read(path, as_version=4)
client = NotebookClient(nb, timeout=timeout, kernel_name="project-python", resources={"metadata": {"path": str(root)}})
t0 = time.time()
client.execute()
nbformat.validate(nb)
out.parent.mkdir(parents=True, exist_ok=True)
nbformat.write(nb, out)
errors = [o for c in nb.cells if c.cell_type == "code" for o in c.outputs if o.output_type == "error"]
assert not errors
print(f"Executed {sum(c.cell_type == 'code' for c in nb.cells)} code cells with no errors "
      f"in {time.time() - t0:.0f}s (mode {mode}).")
print(f"Notebook: {out}")
