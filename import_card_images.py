#!/usr/bin/env python3
"""Import cards from individual camera photos (front + back).

Alternative to the PDF grid pipeline (split_cardlish_pdf.py).
Use this when you have separate photos of each card side.

Usage:
  # Import a single card (2 photos)
  python import_card_images.py --front photo_front.jpg --back photo_back.jpg

  # Import with auto-crop (remove background around card)
  python import_card_images.py --front photo_front.jpg --back photo_back.jpg --auto-crop

  # Import a batch from a directory (naming: card01_front.jpg + card01_back.jpg)
  python import_card_images.py --dir "Card photos/"

  # Dry run (show what would happen, don't write anything)
  python import_card_images.py --front photo_front.jpg --back photo_back.jpg --dry-run
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Configure stdout to use UTF-8 to prevent console encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')

from core.image_import import load_card_image, auto_crop_card, pair_images_from_dir
from core.qr import decode_qr
from core.ocr import CardOCRExtractor
from core.pairing import CardPair, card_sort_key, safe_name
from core.manifest import load_existing_pairs, write_manifest
from core.dist_sync import sync_to_dist

# ── Resolve project root ────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent


def import_single_card(
    front_path: Path,
    back_path: Path,
    out_dir: Path,
    do_auto_crop: bool = False,
    dry_run: bool = False,
) -> CardPair | None:
    """Import one card from a front + back photo pair.

    Args:
        front_path: Path to front side photo.
        back_path: Path to back side photo.
        out_dir: Output directory (e.g. unified_db/).
        do_auto_crop: If True, auto-crop card from background.
        dry_run: If True, only print what would happen.

    Returns:
        The created CardPair, or None on failure.
    """
    print(f"\n📷 Loading images...")
    print(f"   Front: {front_path}")
    print(f"   Back:  {back_path}")

    # Step 1: Load images with EXIF rotation
    front_img = load_card_image(front_path)
    back_img = load_card_image(back_path)
    print(f"   Front size: {front_img.shape[1]}×{front_img.shape[0]}")
    print(f"   Back size:  {back_img.shape[1]}×{back_img.shape[0]}")

    # Step 2: Optional auto-crop
    if do_auto_crop:
        print(f"✂️  Auto-cropping...")
        front_img = auto_crop_card(front_img)
        back_img = auto_crop_card(back_img)
        print(f"   Front cropped: {front_img.shape[1]}×{front_img.shape[0]}")
        print(f"   Back cropped:  {back_img.shape[1]}×{back_img.shape[0]}")

    # Step 3: QR detection on both sides
    print(f"🔍 Detecting QR codes...")
    front_qr = decode_qr(front_img)
    back_qr = decode_qr(back_img)

    # Determine which side is truly front (QR side = front)
    qr_url = ""
    needs_review = False
    review_note = ""

    if front_qr and not back_qr:
        print(f"   ✅ QR found on front side: {front_qr}")
        qr_url = front_qr
    elif back_qr and not front_qr:
        # User labeled them wrong — swap
        print(f"   🔄 QR found on back side — swapping front/back")
        front_img, back_img = back_img, front_img
        front_path, back_path = back_path, front_path
        qr_url = back_qr
    elif front_qr and back_qr:
        print(f"   ⚠️  QR found on BOTH sides — keeping user's assignment")
        qr_url = front_qr
        needs_review = True
        review_note = "Both sides have QR; please review front/back assignment."
    else:
        print(f"   ⚠️  No QR detected on either side — keeping user's assignment")
        needs_review = True
        review_note = "No QR detected; please review front/back assignment."

    # Step 4: OCR card number + label from front
    print(f"📝 Running OCR on front side...")
    import cv2
    import tempfile
    ocr = CardOCRExtractor()

    # Save front to temp file for OCR (OCR expects a file path)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        cv2.imwrite(str(tmp_path), front_img)

    try:
        card_no, label = ocr.extract_card_meta(str(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)

    if card_no:
        print(f"   Card number: {card_no}")
    else:
        print(f"   ⚠️  No card number detected")

    if label:
        print(f"   Label: {label}")

    # Step 5: Generate pair_id
    # IMPORTANT: Always use {card_no}_card format to match core/pairing.py convention.
    # All downstream scripts (download_card_audio, run_ocr_all_cards, extract_vocab_v3,
    # generate_pdf_cards) expect pair_id to end with '_card' suffix.
    if card_no or label:
        name_part = safe_name(label) if label else "card"
        pair_id = f"{card_no}_{name_part}" if card_no else name_part
    else:
        # Fallback: use timestamp
        pair_id = f"img_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    print(f"   Pair ID: {pair_id}")

    if dry_run:
        print(f"\n🏁 DRY RUN — would create card '{pair_id}' but no files written.")
        return None

    # Step 6: Save images
    cards_dir = out_dir / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)

    front_out = cards_dir / f"{pair_id}_front.png"
    back_out = cards_dir / f"{pair_id}_back.png"

    cv2.imwrite(str(front_out), front_img)
    cv2.imwrite(str(back_out), back_img)
    print(f"💾 Saved:")
    print(f"   {front_out}")
    print(f"   {back_out}")

    # Step 7: Create CardPair
    pair = CardPair(
        pair_id=pair_id,
        cell="",        # No grid cell for photo imports
        row=0,
        col=0,
        card_no=card_no,
        label=label,
        qr_url=qr_url,
        front_image=front_out.relative_to(out_dir).as_posix(),
        back_image=back_out.relative_to(out_dir).as_posix(),
        front_page=0,   # No page numbers for photo imports
        back_page=0,
        front_bbox_xyxy=(0, 0, front_img.shape[1], front_img.shape[0]),
        back_bbox_xyxy=(0, 0, back_img.shape[1], back_img.shape[0]),
        needs_review=needs_review,
        review_note=review_note,
        created_at=datetime.now().strftime("%d/%m/%Y"),
        card_id=f"photo_{pair_id}",
        front_cell="",
        back_cell="",
        manual_locked=False,
        source_pdf="photo_import",
    )

    return pair


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import cards from individual camera photos.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Mode 1: Single pair
    parser.add_argument("--front", type=Path, help="Path to front side photo.")
    parser.add_argument("--back", type=Path, help="Path to back side photo.")

    # Mode 2: Batch from directory
    parser.add_argument(
        "--dir", type=Path,
        help="Directory containing paired photos (e.g. card01_front.jpg + card01_back.jpg)."
    )

    # Options
    parser.add_argument(
        "--out", type=Path, default=Path("unified_db"),
        help="Output directory for the card database (default: 'unified_db')."
    )
    parser.add_argument(
        "--auto-crop", action="store_true",
        help="Auto-crop card from background (useful for photos with visible background)."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would happen without writing any files."
    )

    args = parser.parse_args()

    # Validate arguments
    if args.dir:
        # Batch mode
        if not args.dir.is_absolute():
            args.dir = PROJECT_ROOT / args.dir
        if not args.dir.exists():
            print(f"❌ Directory not found: {args.dir}")
            sys.exit(1)
        image_pairs = pair_images_from_dir(args.dir)
        if not image_pairs:
            print(f"❌ No front/back image pairs found in: {args.dir}")
            print(f"   Expected naming: card01_front.jpg + card01_back.jpg")
            print(f"   Or: card01_f.jpg + card01_b.jpg")
            print(f"   Or: card01_truoc.jpg + card01_sau.jpg")
            sys.exit(1)
    elif args.front and args.back:
        # Single pair mode
        if not args.front.exists():
            print(f"❌ Front image not found: {args.front}")
            sys.exit(1)
        if not args.back.exists():
            print(f"❌ Back image not found: {args.back}")
            sys.exit(1)
        image_pairs = [(args.front, args.back)]
    else:
        parser.error("Either --front + --back or --dir is required.")

    # Resolve output directory
    out_dir = args.out if args.out.is_absolute() else PROJECT_ROOT / args.out

    print(f"╔══════════════════════════════════════════════════════════╗")
    print(f"║          📷 Cardlish Photo Card Importer                ║")
    print(f"╠══════════════════════════════════════════════════════════╣")
    print(f"║  Output     : {str(out_dir):<42s} ║")
    print(f"║  Card pairs : {len(image_pairs):<42d} ║")
    print(f"║  Auto-crop  : {'Yes' if args.auto_crop else 'No':<42s} ║")
    print(f"║  Dry run    : {'Yes' if args.dry_run else 'No':<42s} ║")
    print(f"╚══════════════════════════════════════════════════════════╝")

    # Load existing database
    if not args.dry_run:
        print(f"\n📂 Loading existing card database from {out_dir}...")
        existing_pairs = load_existing_pairs(out_dir)
        print(f"   Loaded {len(existing_pairs)} existing card pairs.")
        existing_ids = {p.pair_id for p in existing_pairs}
    else:
        existing_pairs = []
        existing_ids = set()

    # Process each pair
    new_pairs = []
    for i, (front_path, back_path) in enumerate(image_pairs, 1):
        if len(image_pairs) > 1:
            print(f"\n{'='*60}")
            print(f"  [{i}/{len(image_pairs)}] Processing pair")
            print(f"{'='*60}")

        try:
            pair = import_single_card(
                front_path=front_path,
                back_path=back_path,
                out_dir=out_dir,
                do_auto_crop=args.auto_crop,
                dry_run=args.dry_run,
            )
            if pair:
                # Check for ID collision
                if pair.pair_id in existing_ids:
                    print(f"   ⚠️  Card '{pair.pair_id}' already exists — will be updated (overwritten).")
                new_pairs.append(pair)
                existing_ids.add(pair.pair_id)
        except Exception as e:
            print(f"   ❌ Error: {e}")
            continue

    if args.dry_run:
        print(f"\n🏁 DRY RUN complete. No files were written.")
        return

    if not new_pairs:
        print(f"\n⚠️  No new cards were imported.")
        return

    # Merge with existing database
    print(f"\n📝 Merging {len(new_pairs)} new card(s) into database...")
    merged_dict = {p.pair_id: p for p in existing_pairs}
    for p in new_pairs:
        # Preserve created_at if updating existing card
        if p.pair_id in merged_dict:
            p.created_at = merged_dict[p.pair_id].created_at
        merged_dict[p.pair_id] = p

    final_pairs = sorted(merged_dict.values(), key=card_sort_key)

    # Write manifest
    print(f"💾 Writing manifest ({len(final_pairs)} total cards)...")
    write_manifest(final_pairs, out_dir)

    # Sync to dist
    print(f"🔄 Syncing to dist/...")
    dist_dir = PROJECT_ROOT / "dist"
    sync_to_dist(final_pairs, out_dir, dist_dir)

    # Copy to public/data/ as source of truth
    dist_cards_json = dist_dir / "data" / "cards.json"
    public_cards_json = PROJECT_ROOT / "public" / "data" / "cards.json"
    if dist_cards_json.exists():
        shutil.copy2(dist_cards_json, public_cards_json)
        print(f"   Copied dist/data/cards.json → public/data/cards.json (source of truth).")

    # Summary
    print(f"\n╔══════════════════════════════════════════════════════════╗")
    print(f"║                   📊 Import Summary                     ║")
    print(f"╠══════════════════════════════════════════════════════════╣")
    print(f"║  New cards imported : {len(new_pairs):<35d} ║")
    print(f"║  Total database     : {len(final_pairs):<35d} ║")
    review_count = sum(1 for p in new_pairs if p.needs_review)
    print(f"║  Needs review       : {review_count:<35d} ║")
    print(f"╚══════════════════════════════════════════════════════════╝")

    for p in new_pairs:
        print(f"   ✅ {p.pair_id} (card #{p.card_no or '?'})")
        if p.needs_review:
            print(f"      ⚠️  {p.review_note}")


if __name__ == "__main__":
    main()
