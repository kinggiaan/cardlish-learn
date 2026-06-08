from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional
import cv2
import numpy as np
from core.qr import decode_qr

CELL_NAMES = ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3"]

# Gap detection parameters (calibrated on 53 scan pages, 100% accuracy)
WHITE_THRESHOLD = 228       # Pixels brighter than this are "white" (scanner background)
GAP_FRACTION = 0.45         # A gap column/row should have >45% white pixels
EDGE_MARGIN_X_RATIO = 0.10  # Ignore gaps within 10% of left/right edge
EDGE_MARGIN_Y_RATIO = 0.05  # Ignore gaps within 5% of top/bottom edge
MIN_CELL_W_RATIO = 0.20     # Each cell must be at least 20% of image width
MIN_CELL_H_RATIO = 0.15     # Each cell must be at least 15% of image height

@dataclass
class CropInfo:
    page_index: int
    cell: str
    row: int
    col: int
    crop_path: str
    bbox_xyxy: Tuple[int, int, int, int]
    qr_url: str = ""


def _find_white_gaps(
    profile: np.ndarray,
    total_len: int,
    gap_fraction: float = GAP_FRACTION,
) -> List[Tuple[int, int, int, int, float]]:
    """Find contiguous regions where white pixel fraction exceeds threshold.

    Returns list of (start, end, center, width, peak_value) tuples.
    """
    # Smooth the profile to reduce noise
    kernel_size = 11
    kernel = np.ones(kernel_size, dtype=np.float32) / kernel_size
    smooth = np.convolve(profile, kernel, mode="same")

    gaps: List[Tuple[int, int, int, int, float]] = []
    in_gap = False
    gap_start = 0

    for i in range(total_len):
        if smooth[i] > gap_fraction and not in_gap:
            in_gap = True
            gap_start = i
        elif smooth[i] <= gap_fraction and in_gap:
            in_gap = False
            width = i - gap_start
            if width > 3:  # Minimum gap width to filter noise
                center = (gap_start + i) // 2
                peak = float(np.max(smooth[gap_start:i]))
                gaps.append((gap_start, i, center, width, peak))

    # Handle gap extending to the edge
    if in_gap:
        width = total_len - gap_start
        if width > 3:
            center = (gap_start + total_len) // 2
            peak = float(np.max(smooth[gap_start:]))
            gaps.append((gap_start, total_len, center, width, peak))

    return gaps


def _build_grid_from_gaps(
    col_gaps: List[Tuple[int, int, int, int, float]],
    row_gaps: List[Tuple[int, int, int, int, float]],
    img_w: int,
    img_h: int,
) -> Optional[Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]]:
    """Build a 3x3 grid from exactly 2 column gaps and 2 row gaps.

    Returns (cols, rows) where each is a list of 3 (start, end) tuples,
    or None if the resulting grid has invalid cell sizes.
    """
    # Sort by position
    col_gaps = sorted(col_gaps, key=lambda g: g[2])
    row_gaps = sorted(row_gaps, key=lambda g: g[2])

    cols = [
        (0, col_gaps[0][0]),                    # Col 1: left edge → first gap start
        (col_gaps[0][1], col_gaps[1][0]),        # Col 2: first gap end → second gap start
        (col_gaps[1][1], img_w - 1),             # Col 3: second gap end → right edge
    ]
    rows = [
        (0, row_gaps[0][0]),                    # Row 1: top edge → first gap start
        (row_gaps[0][1], row_gaps[1][0]),        # Row 2: first gap end → second gap start
        (row_gaps[1][1], img_h - 1),             # Row 3: second gap end → bottom edge
    ]

    # Validate: all cells must have reasonable sizes
    min_w = int(img_w * MIN_CELL_W_RATIO)
    min_h = int(img_h * MIN_CELL_H_RATIO)
    for r_start, r_end in rows:
        for c_start, c_end in cols:
            if (c_end - c_start) < min_w or (r_end - r_start) < min_h:
                return None

    return cols, rows


def _build_fixed_grid(img_w: int, img_h: int) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """Build a fixed 3x3 equal-size grid as fallback.

    Each cell is exactly 1/3 of the image width and height.
    """
    cell_w = img_w / 3
    cell_h = img_h / 3

    cols = [
        (0, int(cell_w)),
        (int(cell_w), int(2 * cell_w)),
        (int(2 * cell_w), img_w - 1),
    ]
    rows = [
        (0, int(cell_h)),
        (int(cell_h), int(2 * cell_h)),
        (int(2 * cell_h), img_h - 1),
    ]
    return cols, rows


def detect_grid(
    img_bgr: np.ndarray,
) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]], str]:
    """Detect the 3x3 card grid using gap detection with fixed grid fallback.

    Strategy: Find white gaps (scanner background) between cards.
    Cards can be any color (gray, green, pink, etc.) but the gaps between them
    are always white/near-white from the scanner bed.

    Returns:
        (cols, rows, method) where cols and rows are lists of 3 (start, end) tuples,
        and method is "gap_detection" or "fixed_grid".
    """
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # Create white pixel mask (scanner background)
    white_mask = (gray > WHITE_THRESHOLD).astype(np.float32)

    # Project white fraction along each axis
    col_profile = white_mask.mean(axis=0)  # shape: (w,)  — fraction of white per column
    row_profile = white_mask.mean(axis=1)  # shape: (h,)  — fraction of white per row

    # Find gap regions
    col_gaps = _find_white_gaps(col_profile, w)
    row_gaps = _find_white_gaps(row_profile, h)

    # Filter: keep only INTERNAL gaps (not edges of the page)
    margin_x = int(w * EDGE_MARGIN_X_RATIO)
    margin_y = int(h * EDGE_MARGIN_Y_RATIO)
    internal_col_gaps = [g for g in col_gaps if margin_x < g[2] < w - margin_x]
    internal_row_gaps = [g for g in row_gaps if margin_y < g[2] < h - margin_y]

    # We need exactly 2 internal gaps per axis (to divide into 3 sections)
    # If more than 2, pick the 2 with highest peak white fraction
    if len(internal_col_gaps) > 2:
        internal_col_gaps = sorted(internal_col_gaps, key=lambda g: g[4], reverse=True)[:2]
    if len(internal_row_gaps) > 2:
        internal_row_gaps = sorted(internal_row_gaps, key=lambda g: g[4], reverse=True)[:2]

    # Try building grid from detected gaps
    if len(internal_col_gaps) >= 2 and len(internal_row_gaps) >= 2:
        result = _build_grid_from_gaps(internal_col_gaps, internal_row_gaps, w, h)
        if result is not None:
            return result[0], result[1], "gap_detection"

    # Fallback: fixed equal grid
    cols, rows = _build_fixed_grid(w, h)
    return cols, rows, "fixed_grid"


def crop_pages(page_paths: List[Path], out_dir: Path) -> List[CropInfo]:
    raw_cells_dir = out_dir / "raw_cells"
    raw_cells_dir.mkdir(parents=True, exist_ok=True)
    crops: List[CropInfo] = []
    for page_index, page_path in enumerate(page_paths, start=1):
        img = cv2.imread(str(page_path))
        if img is None:
            raise RuntimeError(f"Cannot read rendered page: {page_path}")

        cols, rows, method = detect_grid(img)
        if method == "fixed_grid":
            print(f"  ⚠️  Page {page_index} ({page_path.name}): gap detection failed, using fixed grid")
        else:
            print(f"  ✅ Page {page_index} ({page_path.name}): gap detection OK")

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
