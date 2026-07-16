"""Image import helpers for camera-captured card photos.

Handles:
- EXIF auto-rotation (phone cameras store orientation in EXIF metadata)
- Optional auto-crop to remove background around the card
- Front/back pairing from directory naming conventions
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, List, Tuple
from PIL import Image, ImageOps


def load_card_image(path: Path) -> np.ndarray:
    """Load a card photo with EXIF auto-rotation.

    Phone cameras often store photos in landscape orientation with EXIF
    metadata indicating the correct rotation. This function applies that
    rotation so the image displays correctly.

    Args:
        path: Path to image file (JPEG, PNG, etc.)

    Returns:
        BGR numpy array (OpenCV format), correctly oriented.

    Raises:
        FileNotFoundError: If path doesn't exist.
        RuntimeError: If image cannot be loaded.
    """
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    # Use Pillow for EXIF-aware loading, then convert to OpenCV format
    pil_img = Image.open(path)
    pil_img = ImageOps.exif_transpose(pil_img)  # Apply EXIF rotation

    # Convert to RGB numpy array, then to BGR for OpenCV
    rgb = np.array(pil_img.convert("RGB"))
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    return bgr


def auto_crop_card(
    img_bgr: np.ndarray,
    border_margin: int = 10,
    min_area_ratio: float = 0.15,
) -> np.ndarray:
    """Detect the card boundary and crop out the background.

    Uses edge detection + contour finding to locate the largest rectangular
    object (the card) and crop to it. If detection fails, returns the
    original image unchanged.

    Args:
        img_bgr: BGR image (OpenCV format).
        border_margin: Extra pixels to keep around detected card edge.
        min_area_ratio: Minimum contour area as fraction of image area.
            Contours smaller than this are ignored (noise).

    Returns:
        Cropped BGR image, or original if auto-crop fails.
    """
    h, w = img_bgr.shape[:2]
    img_area = h * w

    # Convert to grayscale and blur to reduce noise
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)

    # Edge detection
    edges = cv2.Canny(blurred, 30, 100)

    # Dilate edges to close gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges = cv2.dilate(edges, kernel, iterations=2)

    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return img_bgr

    # Find the largest contour that's big enough to be a card
    best_contour = None
    best_area = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > img_area * min_area_ratio and area > best_area:
            best_contour = cnt
            best_area = area

    if best_contour is None:
        return img_bgr

    # Get bounding rectangle
    x, y, rw, rh = cv2.boundingRect(best_contour)

    # Add margin (but stay within image bounds)
    x1 = max(0, x - border_margin)
    y1 = max(0, y - border_margin)
    x2 = min(w, x + rw + border_margin)
    y2 = min(h, y + rh + border_margin)

    # Only crop if the result is meaningfully smaller than original
    crop_area = (x2 - x1) * (y2 - y1)
    if crop_area < img_area * 0.95:
        return img_bgr[y1:y2, x1:x2].copy()

    return img_bgr


def pair_images_from_dir(
    dir_path: Path,
) -> List[Tuple[Path, Path]]:
    """Find front/back image pairs from a directory using naming conventions.

    Supported naming patterns (case-insensitive):
    - {name}_front.{ext} + {name}_back.{ext}
    - {name}_f.{ext} + {name}_b.{ext}
    - {name}_truoc.{ext} + {name}_sau.{ext}

    Args:
        dir_path: Directory containing card photos.

    Returns:
        List of (front_path, back_path) tuples.
    """
    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".heic"}

    # Collect all image files
    images = [
        f for f in dir_path.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS
    ]

    # Group by base name (before _front/_back suffix)
    front_map = {}
    back_map = {}

    for img in images:
        stem_lower = img.stem.lower()
        for front_suffix in ("_front", "_f", "_truoc"):
            if stem_lower.endswith(front_suffix):
                base = img.stem[:len(img.stem) - len(front_suffix)]
                front_map[base.lower()] = img
                break
        for back_suffix in ("_back", "_b", "_sau"):
            if stem_lower.endswith(back_suffix):
                base = img.stem[:len(img.stem) - len(back_suffix)]
                back_map[base.lower()] = img
                break

    # Match pairs
    pairs = []
    for base_key in sorted(front_map.keys()):
        if base_key in back_map:
            pairs.append((front_map[base_key], back_map[base_key]))

    return pairs
