"""Execute and validate the report notebook with the active Python environment.

CRSP mode (default) executes the tracked notebook in place: it reads only the aggregate results in results/
(written by `python -m research.run_all`), so it shows no licensed security-level rows. CF_RECOMPUTE=1 reruns every
study first. CF_MODE=demo runs the synthetic demonstration instead and writes output/demo_run.ipynb (git-ignored).
CF_NB_OUT overrides the output path and CF_CELL_TIMEOUT the per-cell timeout in seconds.
"""
import json
import os
import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

mode = os.environ.get("CF_MODE", "crsp")
if mode not in {"demo", "crsp"}:
    raise SystemExit(f"CF_MODE must be crsp or demo, got {mode!r}")
os.environ["CF_MODE"] = mode
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
default_out = path if mode == "crsp" else root / "output" / "demo_run.ipynb"
out = Path(os.environ.get("CF_NB_OUT", default_out)).resolve()
if mode == "demo" and out == path.resolve():
    raise SystemExit("A demo run must not overwrite the tracked empirical notebook; set CF_NB_OUT elsewhere")
timeout = int(os.environ.get("CF_CELL_TIMEOUT", 600 if os.environ.get("CF_RECOMPUTE") != "1" else 7200))

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
