"""
Run OCR on card images to extract text (vocabulary words + IPA).

Features:
  - Incremental: skips cards already in raw_ocr_results.json
  - --force: re-OCR all cards
  - --cards 1,2,3: re-OCR specific cards only

Usage:
  python experiments/run_ocr_all_cards.py              # Only new cards
  python experiments/run_ocr_all_cards.py --force       # Re-OCR everything
  python experiments/run_ocr_all_cards.py --cards 1,5   # Re-OCR specific cards
"""

import json
import sys
import io
import argparse
from pathlib import Path
from rapidocr_onnxruntime import RapidOCR

# Fix Windows console encoding
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass


def load_existing_ocr(ocr_path):
    """Load existing OCR results as a dict keyed by pair_id."""
    if not ocr_path.exists():
        return {}
    with open(ocr_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {entry["pair_id"]: entry for entry in data}


def parse_card_filter(cards_str):
    """Parse --cards argument into a set of pair_ids."""
    if not cards_str:
        return None
    result = set()
    for part in cards_str.split(","):
        part = part.strip()
        if not part:
            continue
        # Support both "1" and "001_card" formats
        if part.endswith("_card") or "_" in part:
            result.add(part)
        else:
            result.add(f"{int(part):03d}_card")
    return result


def main():
    parser = argparse.ArgumentParser(description="Run OCR on card images (incremental)")
    parser.add_argument("--force", action="store_true", help="Re-OCR all cards, ignoring cache")
    parser.add_argument("--cards", type=str, help="Comma-separated card numbers to re-OCR (e.g. 1,2,3)")
    args = parser.parse_args()

    manifest_path = Path("public/data/cards.json")
    cards_dir = Path("unified_db")
    ocr_path = Path("experiments/raw_ocr_results.json")

    if not manifest_path.exists():
        print(f"[ERROR] Manifest not found: {manifest_path}")
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        cards = json.load(f)

    print(f"[INFO] Loaded {len(cards)} cards from manifest.")

    # Load existing OCR results
    existing_ocr = load_existing_ocr(ocr_path)
    print(f"[INFO] Existing OCR results: {len(existing_ocr)} cards")

    # Determine which cards to process
    card_filter = parse_card_filter(args.cards)

    to_process = []
    skipped = 0
    for card in cards:
        pair_id = card.get("pair_id")

        if card_filter:
            # --cards mode: only process specified cards
            if pair_id in card_filter:
                to_process.append(card)
            else:
                skipped += 1
        elif args.force:
            # --force mode: process all
            to_process.append(card)
        else:
            # Default: skip cards already in OCR results
            if pair_id in existing_ocr:
                skipped += 1
            else:
                to_process.append(card)

    if skipped > 0:
        print(f"[SKIP] {skipped} cards already processed (use --force to re-OCR)")

    if not to_process:
        print(f"[DONE] No new cards to process. All {len(cards)} cards already have OCR results.")
        return

    print(f"[RUN]  Processing {len(to_process)} card(s)...")
    print()

    ocr = RapidOCR()
    new_results = {}

    for i, card in enumerate(to_process):
        pair_id = card.get("pair_id")
        front_rel = card.get("front_image")
        back_rel = card.get("back_image")

        front_path = cards_dir / front_rel if front_rel else None
        back_path = cards_dir / back_rel if back_rel else None

        print(f"  [{i+1}/{len(to_process)}] OCR {pair_id}...", end=" ", flush=True)

        front_text = []
        if front_path and front_path.exists():
            res, _ = ocr(str(front_path))
            if res:
                front_text = [{"text": text, "score": float(score), "box": box} for box, text, score in res]

        back_text = []
        if back_path and back_path.exists():
            res, _ = ocr(str(back_path))
            if res:
                back_text = [{"text": text, "score": float(score), "box": box} for box, text, score in res]

        entry = {
            "pair_id": pair_id,
            "card_no": card.get("card_no"),
            "front_ocr": front_text,
            "back_ocr": back_text,
        }
        new_results[pair_id] = entry
        print(f"front={len(front_text)} items, back={len(back_text)} items")

    # Merge: new results overwrite existing for matching pair_ids
    merged = dict(existing_ocr)
    merged.update(new_results)

    # Convert back to list, preserving order from cards.json
    all_pair_ids = [c["pair_id"] for c in cards]
    result_list = []
    for pid in all_pair_ids:
        if pid in merged:
            result_list.append(merged[pid])
    # Add any remaining entries not in cards.json
    seen = set(all_pair_ids)
    for pid, entry in merged.items():
        if pid not in seen:
            result_list.append(entry)

    with open(ocr_path, "w", encoding="utf-8") as f:
        json.dump(result_list, f, ensure_ascii=False, indent=2)

    print(f"\n[DONE] OCR results saved: {ocr_path}")
    print(f"  Total entries: {len(result_list)} (new: {len(new_results)}, existing: {len(existing_ocr)})")


if __name__ == "__main__":
    main()
