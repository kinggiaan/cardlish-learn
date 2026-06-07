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
            pairs.append(
                CardPair(
                    pair_id=d["pair_id"],
                    cell=d["cell"],
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
                )
            )
        return pairs
    except Exception as e:
        print(f"Warning: Failed to load existing manifest: {e}")
        return []

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
