import re
import cv2
import numpy as np
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Tuple
from PIL import Image
from datetime import datetime
from core.grid import CropInfo, CELL_NAMES
from core.ocr import CardOCRExtractor

@dataclass
class CardPair:
    pair_id: str
    cell: str
    row: int
    col: int
    card_no: str
    label: str
    qr_url: str
    front_image: str
    back_image: str
    front_page: int
    back_page: int
    front_bbox_xyxy: Tuple[int, int, int, int]
    back_bbox_xyxy: Tuple[int, int, int, int]
    needs_review: bool
    review_note: str
    created_at: str

def safe_name(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "card"

def card_sort_key(p: CardPair) -> Tuple[int, int, str]:
    """Helper to sort card pairs numerically by card number first, then fallback to string."""
    try:
        return (0, int(p.card_no), p.pair_id)
    except ValueError:
        return (1, 0, p.pair_id)

def is_cell_blank(img_path: Path) -> bool:
    """Detect if a cell crop is a blank scanner background (mostly white and flat)."""
    if not img_path.exists():
        return True
    img = cv2.imread(str(img_path))
    if img is None:
        return True
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mean_val = np.mean(gray)
    std_val = np.std(gray)
    # A blank cell crop has a very high mean (>240) and very low variance (std < 30)
    return mean_val > 240.0 and std_val < 30.0

def build_pairs(
    crops: List[CropInfo], 
    out_dir: Path, 
    ocr_extractor: CardOCRExtractor,
    existing_pairs: List[CardPair] = None
) -> Tuple[List[CardPair], List[CardPair]]:
    """Pair card front/back images, run OCR, skip blank cells, and merge with existing database.
    
    Returns:
        (final_pairs, new_pairs) - where final_pairs is the merged list, and new_pairs is only the current run.
    """
    cards_dir = out_dir / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)

    by_page_cell = {(c.page_index, c.cell): c for c in crops}
    pages = sorted({c.page_index for c in crops})
    if len(pages) % 2 != 0:
        raise ValueError("Expected an even number of pages: each two pages form one front/back batch.")

    new_pairs: List[CardPair] = []
    pair_batch_no = 0
    
    # Calculate a starting batch number offset based on existing coordinate fallbacks
    existing_batches = [
        int(m.group(1)) for p in (existing_pairs or []) 
        for m in [re.match(r"batch(\d+)_", p.pair_id)] if m
    ]
    batch_offset = max(existing_batches) if existing_batches else 0

    # Track processed pair_ids to handle collisions
    processed_ids = {p.pair_id: p for p in (existing_pairs or [])}

    for page_a, page_b in zip(pages[0::2], pages[1::2]):
        pair_batch_no += 1
        for cell in CELL_NAMES:
            a = by_page_cell[(page_a, cell)]
            b = by_page_cell[(page_b, cell)]
            
            # Check if both sides are blank to identify empty/missing card slots
            path_a = out_dir / a.crop_path
            path_b = out_dir / b.crop_path
            if is_cell_blank(path_a) and is_cell_blank(path_b):
                print(f"  Skipping blank slot at cell {cell} (Page {page_a}/{page_b})")
                continue
            
            a_has_qr = bool(a.qr_url)
            b_has_qr = bool(b.qr_url)
            needs_review = False
            note = ""
            
            # Determine front/back based on QR code
            if a_has_qr and not b_has_qr:
                front, back = a, b
                qr_url = a.qr_url
            elif b_has_qr and not a_has_qr:
                front, back = b, a
                qr_url = b.qr_url
            elif a_has_qr and b_has_qr:
                # Both sides have QR. Keep page_a as front but flag it.
                front, back = a, b
                qr_url = a.qr_url
                needs_review = True
                note = "Both sides have QR; please review front/back assignment."
            else:
                # QR detection failed. Keep page_a as front but flag it.
                front, back = a, b
                qr_url = ""
                needs_review = True
                note = "No QR detected; please review front/back assignment."

            card_no = ""
            label = ""
            
            front_src = out_dir / front.crop_path
            back_src = out_dir / back.crop_path
            
            if front_src.exists():
                try:
                    ocr_card_no, ocr_label = ocr_extractor.extract_card_meta(str(front_src))
                    if ocr_card_no:
                        card_no = ocr_card_no
                    if ocr_label:
                        label = ocr_label
                except Exception as e:
                    print(f"Warning: OCR failed for {front_src}: {e}")

            # Fallback naming if OCR didn't find card_no
            base = f"{card_no}_{safe_name(label)}" if card_no or label else f"batch{pair_batch_no + batch_offset:03d}_{cell}"
            
            # Check for ID collision
            if base in processed_ids:
                existing_match = processed_ids[base]
                is_same_slot = (
                    existing_match.front_page == front.page_index and
                    existing_match.back_page == back.page_index and
                    existing_match.cell == cell
                )
                if not is_same_slot:
                    # Different slot but same ID! Append slot suffix to make it unique
                    col_id = f"{base}_dup_p{front.page_index}_{cell}"
                    needs_review = True
                    note = f"Trùng ID với thẻ ở Trang {existing_match.front_page} Ô {existing_match.cell}. Đã tự động đổi tên để tránh ghi đè."
                    print(f"  Warning: Collision detected for ID '{base}'. Renamed new crop to '{col_id}' to prevent overwrite.")
                    base = col_id
            
            front_out = cards_dir / f"{base}_front.png"
            back_out = cards_dir / f"{base}_back.png"
            
            Image.open(front_src).save(front_out)
            Image.open(back_src).save(back_out)

            pair = CardPair(
                pair_id=base,
                cell=cell,
                row=front.row,
                col=front.col,
                card_no=card_no,
                label=label,
                qr_url=qr_url,
                front_image=front_out.relative_to(out_dir).as_posix(),  # Use posix paths (/)
                back_image=back_out.relative_to(out_dir).as_posix(),    # Use posix paths (/)
                front_page=front.page_index,
                back_page=back.page_index,
                front_bbox_xyxy=front.bbox_xyxy,
                back_bbox_xyxy=back.bbox_xyxy,
                needs_review=needs_review,
                review_note=note,
                created_at=datetime.now().strftime("%d/%m/%Y"),
            )
            new_pairs.append(pair)
            processed_ids[base] = pair
            
    # Merge existing pairs with new ones, letting new ones overwrite existing if matching pair_id
    merged_dict = {p.pair_id: p for p in (existing_pairs or [])}
    for p in new_pairs:
        if p.pair_id in merged_dict:
            p.created_at = merged_dict[p.pair_id].created_at
        merged_dict[p.pair_id] = p
        
    # Convert back to list and sort by card number / pair_id
    final_pairs = list(merged_dict.values())
    final_pairs.sort(key=card_sort_key)
    
    return final_pairs, new_pairs
