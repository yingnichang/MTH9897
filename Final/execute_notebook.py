"""Execute and validate the draft using the active Python environment."""
import os
import sys
import json
from pathlib import Path
import nbformat
from nbclient import NotebookClient

root = Path(__file__).resolve().parent
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
nb = nbformat.read(path, as_version=4)
client = NotebookClient(nb, timeout=300, kernel_name="project-python", resources={"metadata": {"path": str(root)}})
client.execute()
nbformat.validate(nb)
nbformat.write(nb, path)
errors = [o for c in nb.cells if c.cell_type == "code" for o in c.outputs if o.output_type == "error"]
assert not errors
print(f"Executed {sum(c.cell_type == 'code' for c in nb.cells)} code cells with no errors.")
print(f"Notebook: {path}")
