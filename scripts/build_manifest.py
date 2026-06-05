#!/usr/bin/env python3
"""
Build manifest script for Cardlish Learn MVP.

Converts the unified_db cards_manifest.json into a web-ready cards.json
with extended fields for audio, clean images, and learning state.

Usage:
    python scripts/build_manifest.py
    python scripts/build_manifest.py --input unified_db/data/cards_manifest.json --output public/data/cards.json
"""

import json
import argparse
from pathlib import Path


def load_manifest(input_path: Path) -> list[dict]:
    """Load the source manifest JSON."""
    with open(input_path, "r", encoding="utf-8") as f:
        return json.load(f)


def transform_card(card: dict) -> dict:
    """Transform a card from the old format to the new web-ready format."""
    pair_id = card.get("pair_id", "")
    card_no = card.get("card_no", "")
    label = card.get("label", "")

    # Build the display label
    display_label = f"{card_no}"
    if label:
        display_label += f" ({label})"

    return {
        "pair_id": pair_id,
        "card_no": card_no,
        "label": label,
        "display_label": display_label,
        "cell": card.get("cell", ""),
        "qr_url": card.get("qr_url", ""),
        "front_image": card.get("front_image", ""),
        "back_image": card.get("back_image", ""),
        "front_image_clean": "",  # To be filled by clean_card_images.py
        "back_image_clean": "",   # To be filled by clean_card_images.py
        "audio": {
            "status": "pending",  # pending | downloaded | missing | error
            "page_url": card.get("qr_url", ""),
            "remote_url": "",
            "local_path": "",
            "content_type": "",
            "downloaded_at": None,
        },
        "learning": {
            "day": None,
            "known": False,
            "last_seen_at": None,
            "review_count": 0,
        },
        "needs_review": card.get("needs_review", False),
        "review_note": card.get("review_note", ""),
    }


def filter_valid_cards(cards: list[dict]) -> list[dict]:
    """Filter out problematic cards (batch OCR failures, etc)."""
    valid = []
    for card in cards:
        pair_id = card.get("pair_id", "")
        # Skip batch-named cards (OCR failures)
        if pair_id.startswith("batch"):
            print(f"  [SKIP] {pair_id} — batch OCR fallback")
            continue
        valid.append(card)
    return valid


def sort_cards(cards: list[dict]) -> list[dict]:
    """Sort cards by card_no numerically."""
    def sort_key(card):
        try:
            return int(card.get("card_no", "9999"))
        except (ValueError, TypeError):
            return 9999
    return sorted(cards, key=sort_key)


def build_manifest(input_path: Path, output_path: Path) -> None:
    """Main build process."""
    print(f"[LOAD] Loading manifest from: {input_path}")
    raw_cards = load_manifest(input_path)
    print(f"   Found {len(raw_cards)} cards total")

    # Filter
    print("[FILTER] Filtering valid cards...")
    valid_cards = filter_valid_cards(raw_cards)
    print(f"   Kept {len(valid_cards)} valid cards")

    # Transform
    print("[TRANSFORM] Transforming to web format...")
    web_cards = [transform_card(card) for card in valid_cards]

    # Sort
    web_cards = sort_cards(web_cards)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(web_cards, f, ensure_ascii=False, indent=2)

    print(f"[DONE] Written {len(web_cards)} cards to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Build web-ready cards.json from source manifest")
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=Path("unified_db/data/cards_manifest.json"),
        help="Path to source cards_manifest.json",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("public/data/cards.json"),
        help="Path to output cards.json",
    )
    args = parser.parse_args()
    build_manifest(args.input, args.output)


if __name__ == "__main__":
    main()
