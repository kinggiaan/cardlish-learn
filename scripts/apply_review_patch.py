#!/usr/bin/env python3
"""
Apply review patches to Cardlish card data.

Patches can come from the Review Editor (exported JSON) or CLI flags.
All changes are stored in review_overrides.json and logged to change_log.json.

Usage:
    python scripts/apply_review_patch.py patch.json              # Apply patch file
    python scripts/apply_review_patch.py --card ID --set k=v     # Set single field
    python scripts/apply_review_patch.py --card ID --swap-faces  # Swap front/back
    python scripts/apply_review_patch.py --card ID --lock        # Lock card
    python scripts/apply_review_patch.py --card ID --unlock      # Unlock card
    python scripts/apply_review_patch.py --list                  # List overrides
    python scripts/apply_review_patch.py patch.json --rebuild    # Apply + rebuild
"""

import argparse
import io
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding for emoji
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OVERRIDES_PATH = PROJECT_ROOT / "unified_db" / "data" / "review_overrides.json"
CHANGELOG_PATH = PROJECT_ROOT / "unified_db" / "data" / "change_log.json"
MANIFEST_PATH = PROJECT_ROOT / "unified_db" / "data" / "cards_manifest.json"
CARDS_DIR = PROJECT_ROOT / "unified_db" / "cards"

# Fields that can be overridden via patches
ALLOWED_FIELDS = {
    "card_no", "label", "qr_url", "needs_review", "review_note",
    "manual_locked", "front_image", "back_image", "hidden",
}


def load_overrides() -> dict:
    """Load existing review_overrides.json."""
    if not OVERRIDES_PATH.exists():
        return {"_version": 1, "_updated_at": "", "overrides": {}}
    try:
        return json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError):
        return {"_version": 1, "_updated_at": "", "overrides": {}}


def save_overrides(data: dict) -> None:
    """Save review_overrides.json."""
    data["_updated_at"] = datetime.now().isoformat()
    OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    OVERRIDES_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_changelog() -> list:
    """Load existing change_log.json."""
    if not CHANGELOG_PATH.exists():
        return []
    try:
        return json.loads(CHANGELOG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return []


def save_changelog(log: list) -> None:
    """Save change_log.json."""
    CHANGELOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHANGELOG_PATH.write_text(
        json.dumps(log, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def append_log(log: list, action: str, pair_id: str, changes: dict = None, source: str = "apply_review_patch.py"):
    """Append an entry to the change log."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "pair_id": pair_id,
        "source": source,
    }
    if changes:
        entry["changes"] = changes
    log.append(entry)


def load_manifest() -> list:
    """Load cards_manifest.json."""
    if not MANIFEST_PATH.exists():
        print(f"❌ Manifest not found: {MANIFEST_PATH}")
        return []
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def save_manifest(cards: list) -> None:
    """Save cards_manifest.json."""
    MANIFEST_PATH.write_text(
        json.dumps(cards, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def apply_patch_file(patch_path: str, overrides_data: dict, changelog: list) -> int:
    """Apply a patch file to overrides. Returns count of cards changed."""
    patch = json.loads(Path(patch_path).read_text(encoding="utf-8"))
    patch_overrides = patch.get("overrides", {})

    count = 0
    for pair_id, fields in patch_overrides.items():
        # Validate fields
        invalid = set(fields.keys()) - ALLOWED_FIELDS
        if invalid:
            print(f"  ⚠️  {pair_id}: ignoring invalid fields: {invalid}")
            fields = {k: v for k, v in fields.items() if k in ALLOWED_FIELDS}

        if not fields:
            continue

        # Merge into overrides
        existing = overrides_data["overrides"].get(pair_id, {})
        changes = {}
        for key, new_val in fields.items():
            old_val = existing.get(key, None)
            if old_val != new_val:
                changes[key] = [old_val, new_val]
            existing[key] = new_val

        overrides_data["overrides"][pair_id] = existing
        if changes:
            append_log(changelog, "override", pair_id, changes)
            count += 1
            print(f"  ✏️  {pair_id}: {', '.join(f'{k}={v}' for k, v in fields.items())}")

    return count


def apply_single_set(card_id: str, field_values: list, overrides_data: dict, changelog: list) -> int:
    """Apply --set field=value pairs. Returns 1 if changed, 0 otherwise."""
    existing = overrides_data["overrides"].get(card_id, {})
    changes = {}

    for fv in field_values:
        if "=" not in fv:
            print(f"  ❌ Invalid format: '{fv}'. Use field=value")
            continue
        field, value = fv.split("=", 1)
        if field not in ALLOWED_FIELDS:
            print(f"  ⚠️  Invalid field: '{field}'. Allowed: {sorted(ALLOWED_FIELDS)}")
            continue

        # Type coercion for booleans
        if field in ("needs_review", "manual_locked", "hidden"):
            value = value.lower() in ("true", "1", "yes")

        old_val = existing.get(field, None)
        if old_val != value:
            changes[field] = [old_val, value]
        existing[field] = value

    if changes:
        overrides_data["overrides"][card_id] = existing
        append_log(changelog, "override", card_id, changes)
        print(f"  ✏️  {card_id}: {', '.join(f'{k}={existing[k]}' for k in changes)}")
        return 1
    return 0


def swap_faces(card_id: str, overrides_data: dict, changelog: list) -> bool:
    """Swap front and back images for a card. Updates manifest + overrides + renames files."""
    manifest = load_manifest()
    card = next((c for c in manifest if c["pair_id"] == card_id), None)
    if not card:
        print(f"  ❌ Card '{card_id}' not found in manifest")
        return False

    front = card["front_image"]
    back = card["back_image"]

    # Rename files on disk
    front_path = PROJECT_ROOT / "unified_db" / front
    back_path = PROJECT_ROOT / "unified_db" / back

    if front_path.exists() and back_path.exists():
        temp_path = front_path.with_suffix(".tmp.png")
        shutil.move(str(front_path), str(temp_path))
        shutil.move(str(back_path), str(front_path))
        shutil.move(str(temp_path), str(back_path))
        print(f"  🔁 Swapped files: {front_path.name} ↔ {back_path.name}")
    else:
        print(f"  ⚠️  Image files not found, swapping references only")

    # Update manifest
    card["front_image"] = back
    card["back_image"] = front
    save_manifest(manifest)

    # Update overrides
    existing = overrides_data["overrides"].get(card_id, {})
    existing["front_image"] = back
    existing["back_image"] = front
    overrides_data["overrides"][card_id] = existing

    append_log(changelog, "swap_faces", card_id, {"front_image": [front, back], "back_image": [back, front]})
    print(f"  ✅ Swapped front/back for {card_id}")
    return True


def list_overrides(overrides_data: dict) -> None:
    """Print current overrides."""
    overrides = overrides_data.get("overrides", {})
    if not overrides:
        print("📋 No overrides currently set.")
        return

    print(f"📋 Current overrides ({len(overrides)} cards):")
    print("─" * 60)
    for pair_id, fields in sorted(overrides.items()):
        field_strs = [f"{k}={v}" for k, v in fields.items()]
        print(f"  {pair_id}: {', '.join(field_strs)}")
    print("─" * 60)
    print(f"Updated: {overrides_data.get('_updated_at', 'never')}")


def rebuild_cards_json():
    """Run dist_sync to rebuild public/data/cards.json from manifest + overrides."""
    try:
        from core.manifest import load_existing_pairs
        from core.dist_sync import sync_to_dist

        pairs = load_existing_pairs(PROJECT_ROOT / "unified_db")
        if not pairs:
            print("  ⚠️  No pairs found in manifest, skipping rebuild")
            return False

        dist_dir = PROJECT_ROOT / "dist"
        public_data = PROJECT_ROOT / "public" / "data"

        # Sync to dist
        sync_to_dist(pairs, PROJECT_ROOT / "unified_db", dist_dir)

        # Copy to public/data (source of truth for dev)
        dist_cards = dist_dir / "data" / "cards.json"
        if dist_cards.exists() and public_data.exists():
            shutil.copy2(str(dist_cards), str(public_data / "cards.json"))
            print(f"  📋 Copied to public/data/cards.json")

        return True
    except Exception as e:
        print(f"  ❌ Rebuild failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Apply review patches to Cardlish card data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("patch_file", nargs="?", help="Path to patch JSON file")
    parser.add_argument("--card", help="Target card pair_id for single operations")
    parser.add_argument("--set", dest="field_values", action="append", default=[],
                        help="Set field=value (can be repeated)")
    parser.add_argument("--swap-faces", action="store_true", help="Swap front/back images")
    parser.add_argument("--lock", action="store_true", help="Lock card (prevent pipeline overwrite)")
    parser.add_argument("--unlock", action="store_true", help="Unlock card")
    parser.add_argument("--hide", action="store_true", help="Hide card from student view")
    parser.add_argument("--unhide", action="store_true", help="Show hidden card")
    parser.add_argument("--list", action="store_true", help="List current overrides")
    parser.add_argument("--rebuild", action="store_true",
                        help="After applying, rebuild cards.json via dist_sync")
    args = parser.parse_args()

    overrides_data = load_overrides()
    changelog = load_changelog()

    # Handle --list
    if args.list:
        list_overrides(overrides_data)
        return

    changes_made = 0

    # Handle patch file
    if args.patch_file:
        print(f"📦 Applying patch: {args.patch_file}")
        changes_made += apply_patch_file(args.patch_file, overrides_data, changelog)

    # Handle --card operations
    if args.card:
        # --set
        if args.field_values:
            changes_made += apply_single_set(args.card, args.field_values, overrides_data, changelog)

        # --lock
        if args.lock:
            changes_made += apply_single_set(args.card, ["manual_locked=true"], overrides_data, changelog)
            print(f"  🔒 Locked: {args.card}")

        # --unlock
        if args.unlock:
            changes_made += apply_single_set(args.card, ["manual_locked=false"], overrides_data, changelog)
            print(f"  🔓 Unlocked: {args.card}")

        # --hide
        if args.hide:
            changes_made += apply_single_set(args.card, ["hidden=true"], overrides_data, changelog)
            print(f"  👁️ Hidden: {args.card}")

        # --unhide
        if args.unhide:
            changes_made += apply_single_set(args.card, ["hidden=false"], overrides_data, changelog)
            print(f"  👁️ Unhidden: {args.card}")

        # --swap-faces
        if args.swap_faces:
            if swap_faces(args.card, overrides_data, changelog):
                changes_made += 1

    if changes_made == 0 and not args.list:
        print("ℹ️  No changes to apply. Use --help for usage.")
        parser.print_help()
        return

    # Save overrides and changelog
    save_overrides(overrides_data)
    save_changelog(changelog)
    print(f"\n✅ Applied {changes_made} change(s)")
    print(f"   Overrides: {OVERRIDES_PATH}")
    print(f"   Changelog: {CHANGELOG_PATH}")

    # Rebuild if requested
    if args.rebuild:
        print("\n🔄 Rebuilding cards.json...")
        rebuild_cards_json()


if __name__ == "__main__":
    main()
