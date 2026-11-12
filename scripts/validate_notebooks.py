from pathlib import Path
import nbformat

for path in Path("notebooks").glob("*.ipynb"):
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)
    for cell in notebook.cells:
        if cell.cell_type == "code":
            compile(cell.source, str(path), "exec")
    print("VALID", path)
