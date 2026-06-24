"""
Extract vocabulary words from raw OCR results.

Features:
  - Incremental: skips cards already in cards_vocab.json (unless _edited=false)
  - --force: re-extract all cards
  - --cards 1,2,3: re-extract specific cards only
  - Preserves entries with _edited=true (manually cleaned data)

Usage:
  python experiments/extract_vocab_v3.py              # Only new cards
  python experiments/extract_vocab_v3.py --force       # Re-extract everything
  python experiments/extract_vocab_v3.py --cards 1,5   # Re-extract specific cards
"""

import json
import re
import sys
import io
import argparse
from pathlib import Path

# Fix Windows console encoding
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass


def get_center(box):
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    return sum(xs)/len(xs), sum(ys)/len(ys)

def clean_word(text):
    text = text.strip()
    text = re.sub(r"^[^a-zA-Z]+|[^a-zA-Z]+$", "", text)
    return text.lower()

def is_word_candidate(text):
    t = text.strip()
    if " " in t or not t or len(t) < 2:
        return False
    if "/" in t:
        return False
    if t.isdigit():
        return False
    if re.match(r"^\d+$", t) or re.match(r"^\d{3}[a-zA-Z]?$", t):
        return False
    if t.endswith("-") or t.startswith("-"):
        return False
    if not re.search(r"[a-zA-Z]", t):
        return False
    vietnamese_words = {"âm", "chữ", "thường", "được", "biểu", "hiện", "bằng", "sau", "đó", "phụ", "cuối", "chú", "ý", "phát"}
    if t.lower() in vietnamese_words:
        return False
    return True

def clean_ipa(text):
    t = text.strip()
    t = t.strip("/")
    return f"/{t}/"

def extract_vocab_for_side(ocr_items):
    items = []
    for item in ocr_items:
        text = item["text"]
        box = item["box"]
        score = item["score"]
        cx, cy = get_center(box)
        items.append({
            "text": text,
            "score": score,
            "cx": cx,
            "cy": cy,
            "box": box
        })

    items.sort(key=lambda x: x["cy"])

    paired = []
    used_item_indices = set()

    word_items = []
    ipa_items = []
    for idx, item in enumerate(items):
        t = item["text"].strip()
        if t.startswith("/") or t.startswith("\\") or t.endswith("/"):
            ipa_items.append((idx, item))
        elif is_word_candidate(t):
            word_items.append((idx, item))

    for w_idx, w in word_items:
        if w_idx in used_item_indices:
            continue
        word_clean = clean_word(w["text"])
        if not word_clean or len(word_clean) < 2:
            continue

        best_ipa_idx = None
        best_ipa_dist = 9999
        for i_idx, ipa in ipa_items:
            if i_idx in used_item_indices:
                continue
            dist = abs(ipa["cy"] - w["cy"])
            if dist < 50 and dist < best_ipa_dist:
                best_ipa_dist = dist
                best_ipa_idx = i_idx

        if best_ipa_idx is not None:
            ipa_clean = clean_ipa(items[best_ipa_idx]["text"])
        else:
            ipa_clean = ""

        paired.append({
            "word": word_clean,
            "ipa": ipa_clean,
            "cy": w["cy"],
            "cx": w["cx"]
        })
        used_item_indices.add(w_idx)
        if best_ipa_idx is not None:
            used_item_indices.add(best_ipa_idx)

    paired_sorted = []
    if paired:
        paired = sorted(paired, key=lambda x: x["cy"])
        rows = []
        current_row = [paired[0]]
        for p in paired[1:]:
            if p["cy"] - current_row[0]["cy"] < 40:
                current_row.append(p)
            else:
                rows.append(current_row)
                current_row = [p]
        rows.append(current_row)

        for row in rows:
            row_sorted = sorted(row, key=lambda x: x["cx"])
            for p in row_sorted:
                paired_sorted.append({
                    "word": p["word"],
                    "ipa": p["ipa"]
                })

    return paired_sorted


def parse_card_filter(cards_str):
    """Parse --cards argument into a set of pair_ids."""
    if not cards_str:
        return None
    result = set()
    for part in cards_str.split(","):
        part = part.strip()
        if not part:
            continue
        if part.endswith("_card") or "_" in part:
            result.add(part)
        else:
            result.add(f"{int(part):03d}_card")
    return result


def main():
    parser = argparse.ArgumentParser(description="Extract vocab from OCR results (incremental)")
    parser.add_argument("--force", action="store_true", help="Re-extract all cards")
    parser.add_argument("--cards", type=str, help="Comma-separated card numbers to re-extract")
    args = parser.parse_args()

    raw_path = Path("experiments/raw_ocr_results.json")
    vocab_path = Path("public/data/cards_vocab.json")

    if not raw_path.exists():
        print("[ERROR] Raw OCR results not found. Run run_ocr_all_cards.py first.")
        return

    with open(raw_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    # Load existing vocab
    existing_vocab = {}
    if vocab_path.exists():
        with open(vocab_path, "r", encoding="utf-8") as f:
            existing_vocab = json.load(f)

    print(f"[INFO] OCR results: {len(results)} cards")
    print(f"[INFO] Existing vocab: {len(existing_vocab)} cards")

    card_filter = parse_card_filter(args.cards)

    to_process = []
    skipped = 0
    skipped_edited = 0

    for entry in results:
        pair_id = entry["pair_id"]

        if card_filter:
            if pair_id in card_filter:
                to_process.append(entry)
            else:
                skipped += 1
        elif args.force:
            # Force mode: still protect _edited entries
            if pair_id in existing_vocab and existing_vocab[pair_id].get("_edited"):
                skipped_edited += 1
            else:
                to_process.append(entry)
        else:
            # Default: skip cards already in vocab
            if pair_id in existing_vocab:
                skipped += 1
            else:
                to_process.append(entry)

    if skipped > 0:
        print(f"[SKIP] {skipped} cards already have vocab (use --force to re-extract)")
    if skipped_edited > 0:
        print(f"[LOCK] {skipped_edited} cards have _edited=true (use --cards X to override)")

    if not to_process:
        print(f"[DONE] No new cards to process. All cards already have vocab data.")
        return

    print(f"[RUN]  Extracting vocab for {len(to_process)} card(s)...")

    new_extracted = {}
    for entry in to_process:
        pair_id = entry["pair_id"]
        front_words = extract_vocab_for_side(entry["front_ocr"])
        back_words = extract_vocab_for_side(entry["back_ocr"])

        new_extracted[pair_id] = {
            "front": front_words,
            "back": back_words,
        }

    # Merge: new results overwrite existing (but keep _edited entries intact unless --cards)
    merged = dict(existing_vocab)
    merged.update(new_extracted)

    with open(vocab_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\n[DONE] Vocab saved: {vocab_path}")
    print(f"  Total entries: {len(merged)} (new: {len(new_extracted)}, existing: {len(existing_vocab)})")

    # Print sample
    for pid in list(new_extracted.keys())[:5]:
        front = [f"{w['word']} {w['ipa']}" for w in new_extracted[pid]["front"]]
        back = [f"{w['word']} {w['ipa']}" for w in new_extracted[pid]["back"]]
        print(f"\n  {pid}:")
        print(f"    Front: {front}")
        print(f"    Back:  {back}")


if __name__ == "__main__":
    main()
