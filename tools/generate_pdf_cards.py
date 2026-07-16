"""
Generate PDF cards for all vocab cards or a specific lesson.

Usage:
  python tools/generate_pdf_cards.py                          # Cards 1-11
  python tools/generate_pdf_cards.py --all                    # All 59 vocab cards
  python tools/generate_pdf_cards.py --cards 1,2,3            # Specific cards
  python tools/generate_pdf_cards.py --lesson lesson_short_a  # By lesson
"""

import os
import sys
import io
import json
import subprocess
import argparse
from pathlib import Path

# Add project root to path for core imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.card_utils import parse_card_filter

# Fix Windows console encoding
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://localhost:8787/tools/print-vocab-cards.html"


def load_data():
    vocab = json.loads((PROJECT_ROOT / "public/data/cards_vocab.json").read_text(encoding="utf-8"))
    lessons = json.loads((PROJECT_ROOT / "public/data/lessons.json").read_text(encoding="utf-8"))
    return vocab, lessons


def resolve_card_ids(args, vocab, lessons):
    all_vocab_ids = sorted(vocab.keys())

    if args.all:
        return all_vocab_ids

    if args.lesson:
        lesson = next((l for l in lessons if l["id"] == args.lesson), None)
        if not lesson:
            print(f"[ERROR] Lesson '{args.lesson}' not found.")
            print(f"  Available: {[l['id'] for l in lessons]}")
            sys.exit(1)
        if lesson["cards"] == "all":
            return all_vocab_ids
        matched = parse_card_filter(",".join(str(n) for n in lesson["cards"]), all_vocab_ids)
        return sorted(matched) if matched else []

    if args.cards:
        matched = parse_card_filter(args.cards, all_vocab_ids)
        return sorted(matched) if matched else []

    # Default: cards 1-11
    matched = parse_card_filter(",".join(str(n) for n in range(1, 12)), all_vocab_ids)
    return sorted(matched) if matched else []


def generate_pdf(card_id, output_file):
    url = f"{BASE_URL}?card={card_id}"

    cmd = [
        CHROME_PATH,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--virtual-time-budget=3000",
        f"--print-to-pdf={output_file.resolve()}",
        url,
    ]

    subprocess.run(cmd, capture_output=True, text=True, check=True)


def main():
    parser = argparse.ArgumentParser(description="Generate A4 PDF vocab cards")
    parser.add_argument("--all", action="store_true", help="Generate for all vocab cards")
    parser.add_argument("--cards", type=str, help="Comma-separated card numbers (e.g. 1,2,3)")
    parser.add_argument("--lesson", type=str, help="Lesson ID (e.g. lesson_short_a)")
    parser.add_argument("-o", "--output", type=Path, default=PROJECT_ROOT / "pdf_cards",
                        help="Output directory (default: pdf_cards/)")
    args = parser.parse_args()

    if not os.path.exists(CHROME_PATH):
        print(f"[ERROR] Chrome not found: {CHROME_PATH}")
        sys.exit(1)

    vocab, lessons = load_data()
    card_ids = resolve_card_ids(args, vocab, lessons)

    if not card_ids:
        print("[ERROR] No matching cards found.")
        sys.exit(1)

    args.output.mkdir(exist_ok=True)
    print(f"[INFO] Output: {args.output.resolve()}")
    print(f"[INFO] Cards: {len(card_ids)}")

    success = 0
    for card_id in card_ids:
        num = card_id.replace("_card", "").replace("_", "-")
        output_file = args.output / f"the-hoc-a4-card-{num}.pdf"
        print(f"  [{card_id}] ...", end=" ", flush=True)
        try:
            generate_pdf(card_id, output_file)
            if output_file.exists() and output_file.stat().st_size > 0:
                print(f"OK ({output_file.stat().st_size:,} bytes)")
                success += 1
            else:
                print("FAILED (empty file)")
        except subprocess.CalledProcessError as e:
            print(f"FAILED: {e}")

    print(f"\n[DONE] {success}/{len(card_ids)} PDFs generated in {args.output}")


if __name__ == "__main__":
    main()
