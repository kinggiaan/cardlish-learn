"""Sync processed card data into the dist/ Cardlish Learn app.

This module:
1. Copies new/updated card images from unified_db/cards/ → dist/cards/
2. Merges the pipeline manifest into dist/data/cards.json, preserving
   extra fields (color, audio, learning, display_label, etc.) that the
   dist app relies on but the pipeline doesn't produce.
"""

import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import List

from core.pairing import CardPair


def sync_to_dist(pairs: List[CardPair], unified_dir: Path, dist_dir: Path) -> None:
    """Sync card images and manifest from unified_db into dist/.

    Args:
        pairs: All card pairs from the pipeline (merged).
        unified_dir: The unified_db output directory (contains cards/, data/).
        dist_dir: The dist/ app directory (contains cards/, data/, index.html, etc.).
    """
    if not dist_dir.exists():
        print(f"  Warning: dist/ directory not found at {dist_dir}. Skipping sync.")
        return

    # ── 1. Sync card images ──────────────────────────────────────
    src_cards = unified_dir / "cards"
    dst_cards = dist_dir / "cards"
    dst_cards.mkdir(parents=True, exist_ok=True)

    synced = 0
    for img in src_cards.glob("*.png"):
        dst_img = dst_cards / img.name
        # Only copy if source is newer or dest doesn't exist
        if not dst_img.exists() or img.stat().st_mtime > dst_img.stat().st_mtime:
            shutil.copy2(img, dst_img)
            synced += 1
    print(f"  Synced {synced} card images to dist/cards/.")

    # ── 2. Merge manifest into dist/data/cards.json ──────────────
    dist_json = dist_dir / "data" / "cards.json"
    dist_json.parent.mkdir(parents=True, exist_ok=True)

    # Load existing dist cards (may have rich metadata)
    existing_dist: dict = {}
    if dist_json.exists():
        try:
            with dist_json.open("r", encoding="utf-8") as f:
                existing_data = json.load(f)
            raw = existing_data if isinstance(existing_data, list) else existing_data.get("cards", [])
            existing_dist = {c["pair_id"]: c for c in raw if "pair_id" in c}
        except Exception as e:
            print(f"  Warning: Could not load existing dist/data/cards.json: {e}")

    # Build merged list
    merged = []
    for pair in pairs:
        pair_dict = asdict(pair)
        pair_id = pair_dict["pair_id"]

        if pair_id in existing_dist:
            # Start from the existing rich record, then overlay pipeline fields
            record = existing_dist[pair_id].copy()
            # Update core fields from pipeline (these are authoritative)
            for key in (
                "pair_id", "cell", "row", "col", "card_no", "label",
                "qr_url", "front_image", "back_image",
                "front_page", "back_page",
                "front_bbox_xyxy", "back_bbox_xyxy",
                "needs_review", "review_note",
            ):
                record[key] = pair_dict[key]
        else:
            # New card — create a minimal record
            record = pair_dict.copy()
            record.setdefault("display_label", pair_dict.get("card_no", ""))
            record.setdefault("audio", {"status": "pending", "local_path": ""})
            record.setdefault("learning", {
                "day": None, "known": False,
                "last_seen_at": None, "review_count": 0
            })
            record.setdefault("color", {"group": "", "hex": "#cccccc", "rgb": [204, 204, 204]})

        merged.append(record)

    # Sort by card_no numerically
    def sort_key(r):
        try:
            return (0, int(r.get("card_no", "0")))
        except (ValueError, TypeError):
            return (1, 0)

    merged.sort(key=sort_key)

    # Write merged JSON
    with dist_json.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"  Updated dist/data/cards.json with {len(merged)} cards.")
