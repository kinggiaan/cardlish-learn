#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║              Cardlish Learn — Build & Deploy Script             ║
╚══════════════════════════════════════════════════════════════════╝

PURPOSE:
    Assembles all assets (HTML/CSS/JS, card images, audio, data)
    into a single `dist/` directory ready for Cloudflare Pages deployment.
    Rewrites asset paths in app.js so everything works from the web root.

USAGE:
    python scripts/build_deploy.py              # Standard build
    python scripts/build_deploy.py --validate   # Validate without building
    python scripts/build_deploy.py --deploy     # Build + deploy to Cloudflare

PROJECT STRUCTURE (what goes where):
    src/                    -> dist/              (HTML, CSS, JS)
    unified_db/cards/*.png  -> dist/cards/        (card images)
    public/audio/           -> dist/audio/        (audio files, RECURSIVE)
    public/audio/vocab/     -> dist/audio/vocab/  (word pronunciation MP3s)
    public/audio/sentences/ -> dist/audio/sentences/ (sentence MP3s)
    public/data/*.json      -> dist/data/         (cards, vocab, lessons, audio map)

PATH REWRITING (app.js CONFIG):
    Dev paths:                    -> Production paths:
    DATA_URL: '../public/data/...'  -> 'data/...'
    CARDS_BASE_PATH: '../unified_db/' -> ''
    AUDIO_BASE_PATH: '../public/'    -> ''

CACHE BUSTING:
    Auto-generates version hash from file contents.
    Updates ?v=xxx in index.html for styles.css and app.js.

IMPORTANT RULES:
    [X] NEVER manually copy files into dist/ — always use this script
    [X] NEVER replace dist/data/cards.json with unified_db/data/cards_manifest.json
       (that file has audio.status='pending' and will break audio playback!)
    [OK] ALWAYS run this script from the project root directory
    [OK] Source of truth for cards data: public/data/cards.json (audio.status='downloaded')
"""

import hashlib
import json
import re
import shutil
import subprocess
import sys
import argparse
from pathlib import Path
from datetime import datetime


# ── Constants ────────────────────────────────────────────────────
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".ogg", ".webm"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

# Expected minimums for validation (prevents silent data loss)
EXPECTED_MIN = {
    "card_images": 50,
    "audio_root": 50,       # card audio files in audio/
    "audio_vocab": 300,     # vocab word MP3s in audio/vocab/
    "audio_sentences": 100, # sentence MP3s in audio/sentences/
    "data_files": 4,        # cards.json, cards_vocab.json, lessons.json, vocab_audio_map.json
}


# ── Helpers ──────────────────────────────────────────────────────
def file_hash(filepath: Path, length: int = 8) -> str:
    """Generate short hash of file contents for cache busting."""
    h = hashlib.md5(filepath.read_bytes()).hexdigest()
    return h[:length]


def count_files(directory: Path, pattern: str = "*") -> int:
    """Count files matching glob pattern in directory."""
    if not directory.exists():
        return 0
    return sum(1 for f in directory.glob(pattern) if f.is_file())


def count_files_recursive(directory: Path, extensions: set) -> int:
    """Count files with given extensions recursively."""
    if not directory.exists():
        return 0
    return sum(1 for f in directory.rglob("*") if f.is_file() and f.suffix.lower() in extensions)


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


# ── Validation ───────────────────────────────────────────────────
def validate_source(src_dir: Path, cards_dir: Path, audio_dir: Path, data_dir: Path) -> list[str]:
    """
    Validate that all source directories and files exist with expected contents.
    Returns list of error messages (empty = all good).
    """
    errors = []
    warnings = []

    # 1. Check source web files
    for name in ("index.html", "app.js", "styles.css"):
        if not (src_dir / name).exists():
            errors.append(f"Missing source file: {src_dir / name}")

    # 2. Check card images
    card_count = count_files(cards_dir, "*.png")
    if card_count == 0:
        errors.append(f"No card images found in {cards_dir}")
    elif card_count < EXPECTED_MIN["card_images"]:
        warnings.append(f"Only {card_count} card images (expected ≥{EXPECTED_MIN['card_images']})")

    # 3. Check audio files (MUST include subdirectories)
    audio_root = count_files(audio_dir, "*.mp3") if audio_dir.exists() else 0
    audio_vocab = count_files(audio_dir / "vocab", "*.mp3") if (audio_dir / "vocab").exists() else 0
    audio_sentences = count_files(audio_dir / "sentences", "*.mp3") if (audio_dir / "sentences").exists() else 0

    if audio_root < EXPECTED_MIN["audio_root"]:
        warnings.append(f"Only {audio_root} root audio files (expected ≥{EXPECTED_MIN['audio_root']})")
    if audio_vocab < EXPECTED_MIN["audio_vocab"]:
        if audio_vocab == 0:
            errors.append(f"No vocab audio found in {audio_dir / 'vocab'} — word pronunciation will be silent!")
        else:
            warnings.append(f"Only {audio_vocab} vocab audio files (expected ≥{EXPECTED_MIN['audio_vocab']})")
    if audio_sentences < EXPECTED_MIN["audio_sentences"]:
        if audio_sentences == 0:
            errors.append(f"No sentence audio found in {audio_dir / 'sentences'} — sentences will be silent!")
        else:
            warnings.append(f"Only {audio_sentences} sentence audio files (expected ≥{EXPECTED_MIN['audio_sentences']})")

    # 4. Check data files
    required_data = ["cards.json", "cards_vocab.json", "lessons.json", "vocab_audio_map.json"]
    for name in required_data:
        fpath = data_dir / name
        if not fpath.exists():
            errors.append(f"Missing data file: {fpath}")
        elif name == "cards.json":
            # Validate cards.json has correct format (audio.status should be 'downloaded')
            try:
                cards = json.loads(fpath.read_text(encoding="utf-8"))
                if isinstance(cards, list) and len(cards) > 0:
                    first_card = cards[0]
                    audio = first_card.get("audio", {})
                    if audio.get("status") == "pending":
                        errors.append(
                            f"CRITICAL: {fpath} has audio.status='pending'!\n"
                            f"   This is the raw manifest file, not the processed one.\n"
                            f"   Audio playback will be completely broken.\n"
                            f"   Expected: audio.status='downloaded' with valid local_path"
                        )
                    elif not audio.get("local_path"):
                        warnings.append(f"First card in {fpath} has empty audio.local_path")
            except (json.JSONDecodeError, KeyError) as e:
                warnings.append(f"Could not validate {fpath}: {e}")

    # 5. Cross-validate card references against actual files
    asset_errors = validate_manifest_assets(data_dir / "cards.json", cards_dir, audio_dir)
    if asset_errors:
        for ae in asset_errors:
            warnings.append(ae)

    # 6. Cross-validate lessons.json card references
    lesson_errors = validate_lessons_cards(data_dir / "lessons.json", data_dir / "cards.json")
    if lesson_errors:
        for le in lesson_errors:
            warnings.append(le)

    # Print results
    if warnings:
        print(f"\n[!] WARNINGS ({len(warnings)}):") 
        for w in warnings:
            print(f"   [!] {w}")

    if errors:
        print(f"\n[X] ERRORS ({len(errors)}):")
        for e in errors:
            print(f"   [X] {e}")

    return errors


def validate_manifest_assets(cards_json_path: Path, cards_dir: Path, audio_dir: Path) -> list[str]:
    """Cross-validate every image/audio reference in cards.json against actual files on disk.
    
    Returns list of warning messages for missing assets.
    """
    if not cards_json_path.exists():
        return []
    
    try:
        cards = json.loads(cards_json_path.read_text(encoding="utf-8"))
    except Exception:
        return ["Could not parse cards.json for asset validation"]
    
    if not isinstance(cards, list):
        return []
    
    warnings = []
    missing_front = 0
    missing_back = 0
    missing_audio = 0
    batch_cards = 0
    
    for card in cards:
        pid = card.get("pair_id", "?")
        
        # Check for batch cards (OCR failures)
        if pid.startswith("batch"):
            batch_cards += 1
        
        # Check front image
        front = card.get("front_image", "")
        if front:
            front_path = cards_dir / Path(front).name
            if not front_path.exists():
                missing_front += 1
        
        # Check back image
        back = card.get("back_image", "")
        if back:
            back_path = cards_dir / Path(back).name
            if not back_path.exists():
                missing_back += 1
        
        # Check audio
        audio = card.get("audio", {})
        if audio.get("status") == "downloaded" and audio.get("local_path"):
            audio_file = audio_dir / Path(audio["local_path"]).name
            if not audio_file.exists():
                missing_audio += 1
    
    if missing_front > 0:
        warnings.append(f"{missing_front} card(s) have missing front_image files")
    if missing_back > 0:
        warnings.append(f"{missing_back} card(s) have missing back_image files")
    if missing_audio > 0:
        warnings.append(f"{missing_audio} card(s) have audio.status=downloaded but file missing")
    if batch_cards > 10:
        warnings.append(f"{batch_cards} batch card(s) detected (OCR failures) — consider reviewing")
    
    # Check for duplicate pair_ids
    pair_ids = [c.get("pair_id", "") for c in cards]
    seen = set()
    dupes = set()
    for pid in pair_ids:
        if pid in seen:
            dupes.add(pid)
        seen.add(pid)
    if dupes:
        warnings.append(f"Duplicate pair_ids found: {', '.join(sorted(dupes))}")
    
    return warnings


def validate_lessons_cards(lessons_json_path: Path, cards_json_path: Path) -> list[str]:
    """Verify that all cards referenced in lessons.json exist in cards.json.
    
    Returns list of warning messages for missing cards in lessons.
    """
    if not lessons_json_path.exists() or not cards_json_path.exists():
        return []
    
    try:
        lessons = json.loads(lessons_json_path.read_text(encoding="utf-8"))
        cards = json.loads(cards_json_path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"Could not parse lessons.json or cards.json: {e}"]
        
    if not isinstance(lessons, list) or not isinstance(cards, list):
        return []
        
    # Get set of all card numbers present in cards.json
    available_cards = set()
    for idx, card in enumerate(cards):
        card_no_val = card.get("card_no", "")
        # Extract digits from card_no
        digits = "".join(c for c in str(card_no_val) if c.isdigit())
        card_num = int(digits) if digits else (idx + 1)
        available_cards.add(card_num)
        
    warnings = []
    for lesson in lessons:
        lesson_id = lesson.get("id", "?")
        lesson_name = lesson.get("name", "?")
        lesson_cards = lesson.get("cards", [])
        
        if lesson_cards == "all":
            continue
            
        if not isinstance(lesson_cards, list):
            warnings.append(f"Lesson '{lesson_name}' ({lesson_id}) has invalid cards field format (expected list or 'all')")
            continue
            
        missing_cards = []
        for cnum in lesson_cards:
            if cnum not in available_cards:
                missing_cards.append(cnum)
                
        if missing_cards:
            warnings.append(
                f"Lesson '{lesson_name}' ({lesson_id}) references non-existent card number(s): "
                f"{', '.join(map(str, missing_cards))}"
            )
            
    return warnings


def validate_dist(dist_dir: Path) -> list[str]:
    """
    Post-build validation: verify dist/ has everything needed.
    Returns list of error messages.
    """
    errors = []

    # Check critical files exist
    for name in ("index.html", "app.js", "styles.css"):
        if not (dist_dir / name).exists():
            errors.append(f"Missing in dist: {name}")

    # Check audio subdirectories
    vocab_dir = dist_dir / "audio" / "vocab"
    sent_dir = dist_dir / "audio" / "sentences"

    if not vocab_dir.exists():
        errors.append("dist/audio/vocab/ directory missing! Vocab word audio won't play.")
    elif count_files(vocab_dir, "*.mp3") == 0:
        errors.append("dist/audio/vocab/ is empty! Vocab word audio won't play.")

    if not sent_dir.exists():
        errors.append("dist/audio/sentences/ directory missing! Sentence audio won't play.")
    elif count_files(sent_dir, "*.mp3") == 0:
        errors.append("dist/audio/sentences/ is empty! Sentence audio won't play.")

    # Check cards.json isn't the wrong file (should be ~48KB - 400KB depending on card count)
    cards_json = dist_dir / "data" / "cards.json"
    if cards_json.exists():
        size = cards_json.stat().st_size
        if size > 500_000:  # >500KB = likely wrong file
            errors.append(
                f"dist/data/cards.json is suspiciously large ({format_size(size)}).\n"
                f"   Expected <500KB from public/data/. Got {format_size(size)}.\n"
                f"   This may be the raw manifest (unified_db/data/cards_manifest.json) "
                f"which will break audio playback!"
            )

    # Check CONFIG values in app.js
    app_js = dist_dir / "app.js"
    if app_js.exists():
        content = app_js.read_text(encoding="utf-8")
        # Verify paths were rewritten
        if "../public/" in content or "../unified_db/" in content:
            errors.append(
                "dist/app.js still contains dev paths (../public/ or ../unified_db/).\n"
                "   Path rewriting may have failed!"
            )

    if errors:
        print(f"\n[X] POST-BUILD VALIDATION FAILED ({len(errors)} errors):")
        for e in errors:
            print(f"   [X] {e}")
    else:
        print("\n[OK] Post-build validation passed")

    return errors


# ── Build Steps ──────────────────────────────────────────────────
def clean_dist(dist_dir: Path) -> None:
    """Remove existing dist directory and recreate it."""
    if dist_dir.exists():
        print(f"[CLEAN] Removing existing {dist_dir}/")
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True)


def copy_web_app(src_dir: Path, dist_dir: Path) -> None:
    """Copy HTML, CSS, and JS files from src/ to dist/."""
    print("[COPY] Web app files (src/ -> dist/)")
    copied = []
    for ext in ("*.html", "*.css", "*.js"):
        for f in src_dir.glob(ext):
            shutil.copy2(f, dist_dir / f.name)
            copied.append(f.name)
    print(f"   {', '.join(copied)}")


def copy_cards(cards_src: Path, dist_dir: Path) -> None:
    """Copy card PNG images to dist/cards/."""
    cards_dst = dist_dir / "cards"
    if not cards_src.exists():
        print(f"[WARN] Cards directory not found: {cards_src}")
        return

    cards_dst.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in cards_src.glob("*.png"):
        shutil.copy2(f, cards_dst / f.name)
        count += 1
    print(f"[COPY] Card images ({cards_src} -> dist/cards/) — {count} files")


def copy_audio(audio_src: Path, dist_dir: Path) -> None:
    """
    Copy audio files to dist/audio/, RECURSIVELY including subdirectories.

    Expected structure:
        public/audio/
        ├── 001_card.mp3 ... NNN_card.mp3   (card pronunciation)
        ├── vocab/                           (word pronunciation)
        │   ├── apple.mp3
        │   └── ...
        └── sentences/                       (sentence pronunciation)
            ├── 2a755ea09f54.mp3
            └── ...
    """
    audio_dst = dist_dir / "audio"
    if not audio_src.exists():
        print(f"[SKIP] Audio directory not found: {audio_src}")
        return

    audio_files = [f for f in audio_src.rglob("*") if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS]
    if not audio_files:
        print("[SKIP] No audio files found")
        return

    audio_dst.mkdir(parents=True, exist_ok=True)
    counts = {"root": 0, "vocab": 0, "sentences": 0, "other": 0}

    for f in audio_files:
        relative = f.relative_to(audio_src)
        dest = audio_dst / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)

        # Track by subdirectory
        parts = relative.parts
        if len(parts) == 1:
            counts["root"] += 1
        elif parts[0] == "vocab":
            counts["vocab"] += 1
        elif parts[0] == "sentences":
            counts["sentences"] += 1
        else:
            counts["other"] += 1

    total = sum(counts.values())
    print(f"[COPY] Audio files ({audio_src} -> dist/audio/) — {total} files")
    print(f"   [card]  card audio:     {counts['root']}")
    print(f"   [word]  vocab words:    {counts['vocab']}")
    print(f"   [sent]  sentences:      {counts['sentences']}")
    if counts["other"]:
        print(f"   [etc]  other:          {counts['other']}")


def copy_data(data_dir: Path, dist_dir: Path) -> None:
    """
    Copy all JSON data files from public/data/ to dist/data/.

    IMPORTANT: Source of truth is public/data/cards.json (audio.status='downloaded').
    Do NOT use unified_db/data/cards_manifest.json (audio.status='pending').
    """
    data_dst = dist_dir / "data"
    data_dst.mkdir(parents=True, exist_ok=True)

    if not data_dir.exists():
        print(f"[WARN] Data directory not found: {data_dir}")
        return

    count = 0
    files_info = []
    for f in data_dir.glob("*.json"):
        shutil.copy2(f, data_dst / f.name)
        count += 1
        files_info.append(f"{f.name} ({format_size(f.stat().st_size)})")

    print(f"[COPY] Data files ({data_dir} -> dist/data/) — {count} files")
    for info in files_info:
        print(f"   {info}")


def rewrite_paths(dist_dir: Path) -> None:
    """
    Rewrite CONFIG paths in dist/app.js for production deployment.

    Transforms dev-relative paths to root-relative paths:
        '../public/data/...'  -> 'data/...'
        '../unified_db/'      -> ''  (images served from /cards/)
        '../public/'          -> ''  (audio served from /audio/)
    """
    app_js = dist_dir / "app.js"
    if not app_js.exists():
        print("[WARN] app.js not found in dist/")
        return

    print("[REWRITE] Asset paths in app.js")
    content = app_js.read_text(encoding="utf-8")

    replacements = [
        (r"DATA_URL:\s*['\"].*?['\"]", "DATA_URL: 'data/cards.json'"),
        (r"VOCAB_URL:\s*['\"].*?['\"]", "VOCAB_URL: 'data/cards_vocab.json'"),
        (r"LESSONS_URL:\s*['\"].*?['\"]", "LESSONS_URL: 'data/lessons.json'"),
        (r"VOCAB_AUDIO_MAP_URL:\s*['\"].*?['\"]", "VOCAB_AUDIO_MAP_URL: 'data/vocab_audio_map.json'"),
        (r"CARDS_BASE_PATH:\s*['\"].*?['\"]", "CARDS_BASE_PATH: ''"),
        (r"AUDIO_BASE_PATH:\s*['\"].*?['\"]", "AUDIO_BASE_PATH: ''"),
    ]

    changed = 0
    for pattern, replacement in replacements:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            print(f"   -> {replacement}")
            changed += 1
        content = new_content

    app_js.write_text(content, encoding="utf-8")
    if changed == 0:
        print("   (no changes needed — paths already correct)")


def update_cache_bust(dist_dir: Path) -> None:
    """
    Update cache-busting version params in index.html based on file content hashes.
    Replaces ?v=X.Y.Z with ?v=<hash> for CSS and JS files.
    """
    index_html = dist_dir / "index.html"
    if not index_html.exists():
        return

    content = index_html.read_text(encoding="utf-8")

    # Generate hashes from actual file contents
    css_file = dist_dir / "styles.css"
    js_file = dist_dir / "app.js"

    if css_file.exists():
        css_hash = file_hash(css_file)
        content = re.sub(r'styles\.css\?v=[^"\']+', f'styles.css?v={css_hash}', content)
        print(f"[CACHE] styles.css?v={css_hash}")

    if js_file.exists():
        js_hash = file_hash(js_file)
        content = re.sub(r'app\.js\?v=[^"\']+', f'app.js?v={js_hash}', content)
        print(f"[CACHE] app.js?v={js_hash}")

    index_html.write_text(content, encoding="utf-8")


def create_headers(dist_dir: Path) -> None:
    """Create _headers file for Cloudflare Pages caching and security."""
    print("[CREATE] _headers")
    headers_content = """\
# Cloudflare Pages Headers
# Auto-generated by build_deploy.py — do not edit manually

# HTML — always fresh
/*.html
  Cache-Control: public, max-age=0, must-revalidate

/
  Cache-Control: public, max-age=0, must-revalidate

# CSS & JS — cache 1 day (cache-busted via ?v=hash)
/*.css
  Cache-Control: public, max-age=86400, stale-while-revalidate=3600

/*.js
  Cache-Control: public, max-age=86400, stale-while-revalidate=3600

# Images — cache 30 days (immutable content)
/cards/*
  Cache-Control: public, max-age=2592000, immutable

# Audio — cache 30 days (immutable content)
/audio/*
  Cache-Control: public, max-age=2592000, immutable

# Data — cache 1 hour
/data/*
  Cache-Control: public, max-age=3600, stale-while-revalidate=600

# Security headers
/*
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
"""
    (dist_dir / "_headers").write_text(headers_content, encoding="utf-8")


def create_redirects(dist_dir: Path) -> None:
    """Create _redirects for Cloudflare Pages."""
    print("[CREATE] _redirects")
    (dist_dir / "_redirects").write_text(
        "# Cloudflare Pages redirects — auto-generated\n", encoding="utf-8"
    )


def print_summary(dist_dir: Path) -> None:
    """Print build summary with file counts and sizes."""
    total_files = 0
    total_size = 0
    categories = {}

    for f in dist_dir.rglob("*"):
        if f.is_file():
            total_files += 1
            size = f.stat().st_size
            total_size += size
            ext = f.suffix or "other"
            categories[ext] = categories.get(ext, 0) + 1

    print(f"\n{'=' * 60}")
    print(f" BUILD COMPLETE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}")
    print(f"   Output:      {dist_dir.resolve()}")
    print(f"   Total files:  {total_files}")
    print(f"   Total size:   {format_size(total_size)}")
    print(f"\n   Breakdown:")
    for ext, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"     {ext:8s}: {count}")
    print(f"\n   Deploy command:")
    print(f"     npx wrangler pages deploy {dist_dir}")
    print(f"{'=' * 60}")


# ── Main ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Build Cardlish Learn for Cloudflare Pages deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/build_deploy.py                 # Standard build
  python scripts/build_deploy.py --validate      # Validate only (no build)
  python scripts/build_deploy.py --deploy        # Build + deploy
  python scripts/build_deploy.py -o my_dist      # Custom output dir
        """,
    )
    parser.add_argument("-o", "--output", type=Path, default=Path("dist"),
                        help="Output directory (default: dist)")
    parser.add_argument("--src", type=Path, default=Path("src"),
                        help="Source web app directory (default: src)")
    parser.add_argument("--cards-dir", type=Path, default=Path("unified_db/cards"),
                        help="Card images directory (default: unified_db/cards)")
    parser.add_argument("--audio-dir", type=Path, default=Path("public/audio"),
                        help="Audio files directory (default: public/audio)")
    parser.add_argument("--data-dir", type=Path, default=Path("public/data"),
                        help="Data JSON directory (default: public/data)")
    parser.add_argument("--validate", action="store_true",
                        help="Only validate source files, don't build")
    parser.add_argument("--deploy", action="store_true",
                        help="Deploy to Cloudflare Pages after building")
    parser.add_argument("--no-validate", action="store_true",
                        help="Skip validation checks")
    args = parser.parse_args()

    print("=" * 60)
    print(" Cardlish Learn — Build for Cloudflare Pages")
    print("=" * 60)

    # ── Step 0: Validate source ──────────────────────────────
    print("\n[VALIDATE] Checking source files...")
    errors = validate_source(args.src, args.cards_dir, args.audio_dir, args.data_dir)

    if args.validate:
        # Validate-only mode
        if errors:
            print(f"\n[X] Validation failed with {len(errors)} error(s). Fix before building.")
            sys.exit(1)
        else:
            print("\n[OK] All source files validated successfully!")
            sys.exit(0)

    if errors and not args.no_validate:
        print(f"\n[X] Validation failed. Run with --no-validate to force build.")
        sys.exit(1)

    # ── Step 1: Clean ────────────────────────────────────────
    print()
    clean_dist(args.output)

    # ── Step 2: Copy all assets ──────────────────────────────
    copy_web_app(args.src, args.output)
    copy_cards(args.cards_dir, args.output)
    copy_audio(args.audio_dir, args.output)
    copy_data(args.data_dir, args.output)

    # ── Step 3: Transform for production ─────────────────────
    rewrite_paths(args.output)
    update_cache_bust(args.output)

    # ── Step 4: Generate deployment config ───────────────────
    create_headers(args.output)
    create_redirects(args.output)

    # ── Step 5: Post-build validation ────────────────────────
    if not args.no_validate:
        post_errors = validate_dist(args.output)
        if post_errors:
            print(f"\n[X] Build completed but validation found {len(post_errors)} issue(s)!")
            print("   Review the errors above before deploying.")
            sys.exit(1)

    # ── Summary ──────────────────────────────────────────────
    print_summary(args.output)

    # ── Step 6: Deploy (optional) ────────────────────────────
    if args.deploy:
        print("\n[DEPLOY] Deploying to Cloudflare Pages...")
        result = subprocess.run(
            ["npx", "wrangler", "pages", "deploy", str(args.output)],
            cwd=str(Path.cwd()),
        )
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
