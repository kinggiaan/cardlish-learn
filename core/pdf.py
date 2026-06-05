from pathlib import Path
from typing import List
import fitz  # PyMuPDF

def render_pdf(pdf_path: Path, out_dir: Path, pdf_name: str, dpi: int = 200) -> List[Path]:
    """Render PDF pages into PNG images prefixed with the PDF filename."""
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    page_paths: List[Path] = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        out_path = out_dir / f"{pdf_name}_page_{i:03d}.png"
        pix.save(str(out_path))
        page_paths.append(out_path)
    return page_paths
