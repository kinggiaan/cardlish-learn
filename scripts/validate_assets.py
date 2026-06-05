#!/usr/bin/env python3
"""
Validate Cardlish assets before deploy.

Checks:
- Each card has a unique pair_id
- Front/back images exist on disk
- Audio files exist when status == "downloaded"
- No path starts with "../"
- Reports summary with OK / warnings / errors

Usage:
    python scripts/validate_assets.py \
        --manifest public/data/cards.json \
        --cards-dir unified_db/cards \
        --audio-dir public/audio
"""

import argparse
import io
import json
import sys
from pathlib import Path

# Fix Windows console encoding for emoji
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def validate(manifest_path: str, cards_dir: str, audio_dir: str) -> bool:
    """Validate manifest and assets. Returns True if all checks pass."""

    manifest = Path(manifest_path)
    cards_root = Path(cards_dir)
    audio_root = Path(audio_dir)

    if not manifest.exists():
        print(f"❌ Manifest not found: {manifest}")
        return False

    with open(manifest, "r", encoding="utf-8") as f:
        cards = json.load(f)

    if not isinstance(cards, list):
        print("❌ Manifest root is not a JSON array")
        return False

    print(f"📋 Manifest: {manifest}")
    print(f"📁 Cards dir: {cards_root}")
    print(f"🔊 Audio dir: {audio_root}")
    print(f"📊 Total entries: {len(cards)}")
    print("─" * 50)

    errors = []
    warnings = []
    ok_count = 0

    # Check 1: unique pair_id
    pair_ids = [c.get("pair_id", "") for c in cards]
    seen = set()
    for pid in pair_ids:
        if pid in seen:
            errors.append(f"Duplicate pair_id: {pid}")
        seen.add(pid)

    for i, card in enumerate(cards):
        pair_id = card.get("pair_id", f"[index {i}]")

        # Check 2: no ../ paths
        for field in ["front_image", "back_image"]:
            val = card.get(field, "")
            if val and val.startswith("../"):
                errors.append(f"{pair_id}: {field} has ../ path: {val}")

        audio = card.get("audio", {})
        local_path = audio.get("local_path", "")
        if local_path and local_path.startswith("../"):
            errors.append(f"{pair_id}: audio.local_path has ../ path: {local_path}")

        # Check 3: front_image exists
        front = card.get("front_image", "")
        if front:
            front_path = cards_root / Path(front).name
            if not front_path.exists():
                errors.append(f"{pair_id}: front_image not found: {front_path}")
            else:
                ok_count += 1
        else:
            warnings.append(f"{pair_id}: no front_image")

        # Check 4: back_image exists
        back = card.get("back_image", "")
        if back:
            back_path = cards_root / Path(back).name
            if not back_path.exists():
                errors.append(f"{pair_id}: back_image not found: {back_path}")
            else:
                ok_count += 1
        else:
            warnings.append(f"{pair_id}: no back_image")

        # Check 5: audio file exists if downloaded
        audio_status = audio.get("status", "")
        if audio_status == "downloaded":
            if local_path:
                audio_file = audio_root / Path(local_path).name
                if not audio_file.exists():
                    errors.append(
                        f"{pair_id}: audio status=downloaded but file missing: {audio_file}"
                    )
                else:
                    ok_count += 1
            else:
                warnings.append(
                    f"{pair_id}: audio status=downloaded but no local_path"
                )
        elif audio_status in ("missing", "error", "pending"):
            warnings.append(f"{pair_id}: audio status={audio_status}")

    # Check 6: batch cards (OCR failures)
    batch_cards = [c for c in cards if c.get("pair_id", "").startswith("batch")]
    if batch_cards:
        warnings.append(
            f"{len(batch_cards)} batch card(s) detected (OCR failures): "
            + ", ".join(c["pair_id"] for c in batch_cards)
        )

    # Summary
    print()
    if errors:
        print(f"❌ ERRORS ({len(errors)}):")
        for e in errors:
            print(f"   • {e}")
        print()

    if warnings:
        print(f"⚠️  WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"   • {w}")
        print()

    total_cards = len(cards)
    valid_cards = total_cards - len(
        [c for c in cards if c.get("pair_id", "").startswith("batch")]
    )

    print("─" * 50)
    print(f"📊 Summary:")
    print(f"   Total cards: {total_cards}")
    print(f"   Valid cards: {valid_cards}")
    print(f"   Assets OK:   {ok_count}")
    print(f"   Errors:      {len(errors)}")
    print(f"   Warnings:    {len(warnings)}")

    if errors:
        print(f"\n🚫 VALIDATION FAILED — {len(errors)} error(s) found")
        return False
    else:
        print(f"\n✅ VALIDATION PASSED")
        return True


def main():
    parser = argparse.ArgumentParser(description="Validate Cardlish assets")
    parser.add_argument(
        "--manifest",
        default="public/data/cards.json",
        help="Path to cards.json manifest",
    )
    parser.add_argument(
        "--cards-dir",
        default="unified_db/cards",
        help="Directory containing card images",
    )
    parser.add_argument(
        "--audio-dir",
        default="public/audio",
        help="Directory containing audio files",
    )
    args = parser.parse_args()

    success = validate(args.manifest, args.cards_dir, args.audio_dir)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
