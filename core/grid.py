from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional
import cv2
import numpy as np
from core.qr import decode_qr

CELL_NAMES = ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3"]

@dataclass
class CropInfo:
    page_index: int
    cell: str
    row: int
    col: int
    crop_path: str
    bbox_xyxy: Tuple[int, int, int, int]
    qr_url: str = ""

def smooth_projection(values: np.ndarray, kernel_size: int = 31) -> np.ndarray:
    if kernel_size % 2 == 0:
        kernel_size += 1
    kernel = np.ones(kernel_size, dtype=np.float32) / kernel_size
    return np.convolve(values, kernel, mode="same")

def segments_from_projection(
    values: np.ndarray,
    threshold: float,
    min_len: int,
) -> List[Tuple[int, int]]:
    mask = values > threshold
    segments: List[Tuple[int, int]] = []
    start: Optional[int] = None
    for i, on in enumerate(mask):
        if on and start is None:
            start = i
        last = i == len(mask) - 1
        if start is not None and ((not on) or last):
            end = i if last and on else i - 1
            if end - start + 1 >= min_len:
                segments.append((start, end))
            start = None
    return segments

def find_grid_segments(
    img_bgr: np.ndarray,
    expected: int = 3,
    gray_threshold: int = 240,
    projection_threshold: float = 0.12,
) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """Detect 3 column and 3 row bands from a scan page."""
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    dark_mask = gray < gray_threshold

    col_proj = smooth_projection(dark_mask.mean(axis=0), kernel_size=max(31, w // 60))
    row_proj = smooth_projection(dark_mask.mean(axis=1), kernel_size=max(31, h // 60))

    cols = segments_from_projection(col_proj, projection_threshold, min_len=w // 10)
    rows = segments_from_projection(row_proj, projection_threshold, min_len=h // 10)

    # Fallback: fixed thirds if detection fails.
    if len(cols) != expected:
        cols = [(0, int(w * 0.31)), (int(w * 0.33), int(w * 0.68)), (int(w * 0.70), w - 1)]
    if len(rows) != expected:
        rows = [(0, int(h * 0.31)), (int(h * 0.33), int(h * 0.66)), (int(h * 0.70), h - 1)]

    return cols[:expected], rows[:expected]

def crop_pages(page_paths: List[Path], out_dir: Path) -> List[CropInfo]:
    raw_cells_dir = out_dir / "raw_cells"
    raw_cells_dir.mkdir(parents=True, exist_ok=True)
    crops: List[CropInfo] = []
    for page_index, page_path in enumerate(page_paths, start=1):
        img = cv2.imread(str(page_path))
        if img is None:
            raise RuntimeError(f"Cannot read rendered page: {page_path}")
        cols, rows = find_grid_segments(img)
        idx = 0
        for r, (y1, y2) in enumerate(rows):
            for c, (x1, x2) in enumerate(cols):
                cell = CELL_NAMES[idx]
                idx += 1
                crop = img[y1 : y2 + 1, x1 : x2 + 1]
                qr_url = decode_qr(crop)
                
                # Name the crop with page_path.stem to prevent overwriting across different scan files
                crop_path = raw_cells_dir / f"{page_path.stem}_{cell}.png"
                cv2.imwrite(str(crop_path), crop)
                crops.append(
                    CropInfo(
                        page_index=page_index,
                        cell=cell,
                        row=r + 1,
                        col=c + 1,
                        crop_path=str(crop_path.relative_to(out_dir)),
                        bbox_xyxy=(int(x1), int(y1), int(x2), int(y2)),
                        qr_url=qr_url,
                    )
                )
    return crops
