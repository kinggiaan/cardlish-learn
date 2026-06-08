#!/usr/bin/env python3
"""
Split a Cardlish-style PDF scan into 9 paired two-sided cards per page pair.

Expected input layout:
- Each PDF page contains a 3 x 3 grid of card images.
- Page 1 and page 2 are the two sides of the same 9 cards in the same cell positions.
- The front side contains a QR code; the back side does not.

Usage:
  python split_cardlish_pdf.py scan0002.pdf --out out_cardlish --dpi 200
"""

import argparse
import shutil
from pathlib import Path
import sys

# Configure stdout to use UTF-8 to prevent console encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')

# Import core modules
from core.pdf import render_pdf
from core.grid import crop_pages
from core.ocr import CardOCRExtractor
from core.pairing import build_pairs
from core.manifest import write_manifest, load_existing_pairs
from core.contact_sheet import make_review_contact_sheet
from core.dist_sync import sync_to_dist
from core.html_viewer import make_html_viewer

def main() -> None:
    parser = argparse.ArgumentParser(description="Split Cardlish PDF scans into paired card images with OCR ID tagging.")
    parser.add_argument("pdf", type=Path, help="Path to the scanned PDF file.")
    parser.add_argument("--out", type=Path, default=Path("cardlish_output"), help="Output directory path.")
    parser.add_argument("--dpi", type=int, default=200, help="DPI resolution for rendering PDF pages.")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    pdf_name = args.pdf.stem  # Extract the name of the PDF without extension (e.g. scan0002)
    
    print(f"Loading existing card database from {args.out}...")
    existing_pairs = load_existing_pairs(args.out)
    print(f"  Loaded {len(existing_pairs)} existing card pairs.")

    print(f"Step 1: Rendering PDF pages to images (Prefix: {pdf_name})...")
    page_paths = render_pdf(args.pdf, args.out / "rendered_pages", pdf_name, dpi=args.dpi)
    print(f"  Rendered {len(page_paths)} pages.")

    print("Step 2: Cropping pages into raw cell images...")
    crops = crop_pages(page_paths, args.out)
    print(f"  Cropped {len(crops)} cell images.")

    print("Step 3: Initializing OCR engine...")
    ocr_extractor = CardOCRExtractor()

    print("Step 4: Pairing cards, running OCR, and merging into database...")
    final_pairs, new_pairs = build_pairs(crops, args.out, ocr_extractor, existing_pairs)
    print(f"  Processed {len(new_pairs)} new card pairs.")
    print(f"  Consolidated database now contains {len(final_pairs)} card pairs.")

    print("Step 5: Writing updated manifests...")
    write_manifest(final_pairs, args.out)

    print(f"Step 6: Generating review contact sheet for current scan (review_contact_sheet_{pdf_name}.png)...")
    make_review_contact_sheet(new_pairs, args.out, pdf_name)

    print("Step 7: Syncing cards and manifest to dist/ and public/ data (source of truth)...")
    # Always resolve dist/ relative to the project root (script location),
    # not relative to the PDF file which may be in a subfolder like "Card scan/".
    project_root = Path(__file__).resolve().parent
    dist_dir = project_root / "dist"
    sync_to_dist(final_pairs, args.out, dist_dir)
    
    # Copy generated cards.json back to public/data/cards.json as source of truth
    shutil.copy2(dist_dir / "data" / "cards.json", project_root / "public" / "data" / "cards.json")
    print("  Copied dist/data/cards.json -> public/data/cards.json (source of truth).")

    print("Step 8: Regenerating HTML viewer...")
    make_html_viewer(final_pairs, args.out)

    new_review_count = sum(1 for p in new_pairs if p.needs_review)
    new_ocr_count = sum(1 for p in new_pairs if p.card_no)
    
    print("\nProcessing complete!")
    print(f"----------------------------------------")
    print(f"Current PDF Processed : {args.pdf.name}")
    print(f"New Card Pairs Added  : {len(new_pairs)} (OCR tagged: {new_ocr_count})")
    print(f"Total Database Cards  : {len(final_pairs)}")
    print(f"New Cards for Review  : {new_review_count}")
    print(f"Output Location       : {args.out.resolve()}")
    print(f"Viewer                : dist/index.html")
    print(f"----------------------------------------")

if __name__ == "__main__":
    main()
