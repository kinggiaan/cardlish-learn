import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import List
from core.pairing import CardPair

def load_existing_pairs(out_dir: Path) -> List[CardPair]:
    """Load existing card pairs from data/cards_manifest.json if it exists."""
    json_path = out_dir / "data" / "cards_manifest.json"
    if not json_path.exists():
        return []
    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        pairs = []
        for d in data:
            cell_val = d.get("cell", "")
            pairs.append(
                CardPair(
                    pair_id=d["pair_id"],
                    cell=cell_val,
                    row=d["row"],
                    col=d["col"],
                    card_no=d["card_no"],
                    label=d["label"],
                    qr_url=d["qr_url"],
                    front_image=d["front_image"],
                    back_image=d["back_image"],
                    front_page=d["front_page"],
                    back_page=d["back_page"],
                    front_bbox_xyxy=tuple(d["front_bbox_xyxy"]),
                    back_bbox_xyxy=tuple(d["back_bbox_xyxy"]),
                    needs_review=d["needs_review"],
                    review_note=d.get("review_note", ""),
                    created_at=d.get("created_at", "04/06/2026"),
                    # Phase-1 fields (auto-fill for old manifests)
                    card_id=d.get("card_id", f"legacy_{d['pair_id']}"),
                    front_cell=d.get("front_cell", cell_val),
                    back_cell=d.get("back_cell", cell_val),
                    manual_locked=d.get("manual_locked", False),
                    source_pdf=d.get("source_pdf", ""),
                )
            )
        return pairs
    except Exception as e:
        print(f"Warning: Failed to load existing manifest: {e}")
        return []

def cleanup_unreferenced_images(pairs: List[CardPair], out_dir: Path) -> None:
    """Delete image files in cards/ directory that are no longer referenced in the manifest."""
    cards_dir = out_dir / "cards"
    if not cards_dir.exists():
        return
        
    # Collect all active image paths (just the filenames)
    referenced_files = set()
    for p in pairs:
        if p.front_image:
            referenced_files.add(Path(p.front_image).name)
        if p.back_image:
            referenced_files.add(Path(p.back_image).name)
            
    # Iterate through files in cards_dir and delete unreferenced PNGs
    deleted_count = 0
    for f in cards_dir.glob("*.png"):
        if f.name not in referenced_files:
            try:
                f.unlink()
                deleted_count += 1
            except Exception as e:
                print(f"Warning: Failed to delete unreferenced image {f}: {e}")
                
    if deleted_count > 0:
        print(f"Cleanup: Deleted {deleted_count} unreferenced image crops from {cards_dir}")

def write_manifest(pairs: List[CardPair], out_dir: Path) -> None:
    """Write the card manifest to JSON and CSV files."""
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / "cards_manifest.csv"
    json_path = data_dir / "cards_manifest.json"
    
    rows = [asdict(p) for p in pairs]
    
    # Save as JSON
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
        
    # Save as CSV
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = list(rows[0].keys()) if rows else []
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Cleanup unreferenced card images
    cleanup_unreferenced_images(pairs, out_dir)
