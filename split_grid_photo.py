#!/usr/bin/env python3
"""
Split camera photos of a 3x3 card grid into individual paired cards.

Works like split_cardlish_pdf.py but accepts JPG/PNG images instead of PDF.
Input: 2 images (front grid photo + back grid photo).
The grid is split into 3x3 = 9 cells. Empty cells are auto-detected and skipped.

Usage:
  python split_grid_photo.py front_016_022.jpg back_016_022.jpg
"""

import argparse
import shutil
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8')

from core.grid import crop_pages
from core.ocr import CardOCRExtractor
from core.pairing import build_pairs
from core.manifest import write_manifest, load_existing_pairs
from core.contact_sheet import make_review_contact_sheet
from core.dist_sync import sync_to_dist
from core.html_viewer import make_html_viewer


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split camera photos of a 3x3 card grid into paired card images."
    )
    parser.add_argument("front", type=Path, help="Path to front side grid photo (JPG/PNG).")
    parser.add_argument("back", type=Path, help="Path to back side grid photo (JPG/PNG).")
    parser.add_argument("--out", type=Path, default=Path("unified_db"), help="Output directory path.")
    parser.add_argument("--name", type=str, default=None,
                        help="Batch name prefix (default: derived from front filename).")
    args = parser.parse_args()

    for img_path in [args.front, args.back]:
        if not img_path.exists():
            print(f"Error: File not found: {img_path}")
            sys.exit(1)

    args.out.mkdir(parents=True, exist_ok=True)
    batch_name = args.name or args.front.stem

    print(f"Loading existing card database from {args.out}...")
    existing_pairs = load_existing_pairs(args.out)
    print(f"  Loaded {len(existing_pairs)} existing card pairs.")

    # Instead of render_pdf(), we save the images as rendered "pages"
    # Page 1 = front, Page 2 = back (same as PDF pipeline convention)
    rendered_dir = args.out / "rendered_pages"
    rendered_dir.mkdir(parents=True, exist_ok=True)

    # Copy images to rendered_pages with standardized names
    import cv2
    for idx, (src, label) in enumerate([(args.front, "front"), (args.back, "back")], start=1):
        dest = rendered_dir / f"{batch_name}_page_{idx:03d}.png"
        img = cv2.imread(str(src))
        if img is None:
            print(f"Error: Cannot read image: {src}")
            sys.exit(1)
        cv2.imwrite(str(dest), img)
        print(f"  Page {idx} ({label}): {src.name} -> {dest.name} ({img.shape[1]}x{img.shape[0]})")

    page_paths = sorted(rendered_dir.glob(f"{batch_name}_page_*.png"))
    print(f"Step 1: Loaded {len(page_paths)} pages from camera photos.")

    print("Step 2: Cropping pages into raw cell images...")
    crops = crop_pages(page_paths, args.out)
    print(f"  Cropped {len(crops)} cell images.")

    print("Step 3: Initializing OCR engine...")
    ocr_extractor = CardOCRExtractor()

    print("Step 4: Pairing cards, running OCR, and merging into database...")
    final_pairs, new_pairs = build_pairs(crops, args.out, ocr_extractor, existing_pairs, pdf_stem=batch_name)
    print(f"  Processed {len(new_pairs)} new card pairs.")
    print(f"  Consolidated database now contains {len(final_pairs)} card pairs.")

    print("Step 5: Writing updated manifests...")
    write_manifest(final_pairs, args.out)

    print(f"Step 6: Generating review contact sheet...")
    make_review_contact_sheet(new_pairs, args.out, batch_name)

    print("Step 7: Syncing cards and manifest to dist/ and public/ data...")
    project_root = Path(__file__).resolve().parent
    dist_dir = project_root / "dist"
    sync_to_dist(final_pairs, args.out, dist_dir)

    shutil.copy2(dist_dir / "data" / "cards.json", project_root / "public" / "data" / "cards.json")
    print("  Copied dist/data/cards.json -> public/data/cards.json (source of truth).")

    print("Step 8: Regenerating HTML viewer...")
    make_html_viewer(final_pairs, args.out)

    new_review_count = sum(1 for p in new_pairs if p.needs_review)
    new_ocr_count = sum(1 for p in new_pairs if p.card_no)

    print("\nProcessing complete!")
    print(f"----------------------------------------")
    print(f"Photos Processed      : {args.front.name} + {args.back.name}")
    print(f"New Card Pairs Added  : {len(new_pairs)} (OCR tagged: {new_ocr_count})")
    print(f"Total Database Cards  : {len(final_pairs)}")
    print(f"New Cards for Review  : {new_review_count}")
    print(f"Output Location       : {args.out.resolve()}")
    print(f"----------------------------------------")


if __name__ == "__main__":
    main()
