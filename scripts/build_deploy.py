#!/usr/bin/env python3
"""
Build script for Cloudflare Pages deployment.

Assembles all assets into a single `dist/` directory ready for deployment.
Rewrites asset paths in app.js so everything works from the web root.

Usage:
    python scripts/build_deploy.py
    python scripts/build_deploy.py --output dist
"""

import json
import re
import shutil
import argparse
from pathlib import Path


def clean_dist(dist_dir: Path) -> None:
    """Remove existing dist directory."""
    if dist_dir.exists():
        print(f"[CLEAN] Removing existing {dist_dir}/")
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True)


def copy_web_app(src_dir: Path, dist_dir: Path) -> None:
    """Copy HTML, CSS, and JS files to dist."""
    print("[COPY] Web app files (src/ -> dist/)")
    for ext in ("*.html", "*.css", "*.js"):
        for f in src_dir.glob(ext):
            shutil.copy2(f, dist_dir / f.name)
            print(f"   {f.name}")


def copy_cards(cards_src: Path, dist_dir: Path) -> None:
    """Copy card images to dist/cards/."""
    cards_dst = dist_dir / "cards"
    if not cards_src.exists():
        print(f"[WARN] Cards directory not found: {cards_src}")
        return

    print(f"[COPY] Card images ({cards_src} -> dist/cards/)")
    cards_dst.mkdir(parents=True, exist_ok=True)

    count = 0
    for f in cards_src.glob("*.png"):
        shutil.copy2(f, cards_dst / f.name)
        count += 1
    print(f"   {count} images copied")


def copy_audio(audio_src: Path, dist_dir: Path) -> None:
    """Copy audio files to dist/audio/."""
    audio_dst = dist_dir / "audio"
    if not audio_src.exists():
        print(f"[INFO] Audio directory not found: {audio_src} (skipping)")
        return

    audio_files = list(audio_src.glob("*.*"))
    if not audio_files:
        print("[INFO] No audio files found (skipping)")
        return

    print(f"[COPY] Audio files ({audio_src} -> dist/audio/)")
    audio_dst.mkdir(parents=True, exist_ok=True)

    count = 0
    for f in audio_files:
        if f.suffix.lower() in (".mp3", ".m4a", ".wav", ".ogg", ".webm"):
            shutil.copy2(f, audio_dst / f.name)
            count += 1
    print(f"   {count} audio files copied")


def copy_data(data_src: Path, dist_dir: Path) -> None:
    """Copy cards.json, cards_vocab.json, lessons.json, and vocab_audio_map.json to dist/data/."""
    data_dst = dist_dir / "data"
    data_dst.mkdir(parents=True, exist_ok=True)

    if data_src.exists():
        print(f"[COPY] Data ({data_src} -> dist/data/cards.json)")
        shutil.copy2(data_src, data_dst / "cards.json")
    else:
        print(f"[WARN] Manifest not found: {data_src}")

    vocab_src = data_src.parent / "cards_vocab.json"
    if vocab_src.exists():
        print(f"[COPY] Vocab Data ({vocab_src} -> dist/data/cards_vocab.json)")
        shutil.copy2(vocab_src, data_dst / "cards_vocab.json")
    else:
        print(f"[WARN] Vocabulary file not found: {vocab_src}")

    lessons_src = data_src.parent / "lessons.json"
    if lessons_src.exists():
        print(f"[COPY] Lessons ({lessons_src} -> dist/data/lessons.json)")
        shutil.copy2(lessons_src, data_dst / "lessons.json")
    else:
        print(f"[WARN] Lessons file not found: {lessons_src}")

    vocab_audio_map_src = data_src.parent / "vocab_audio_map.json"
    if vocab_audio_map_src.exists():
        print(f"[COPY] Vocab Audio Map ({vocab_audio_map_src} -> dist/data/vocab_audio_map.json)")
        shutil.copy2(vocab_audio_map_src, data_dst / "vocab_audio_map.json")
    else:
        print(f"[WARN] Vocab Audio Map file not found: {vocab_audio_map_src}")


def rewrite_paths(dist_dir: Path) -> None:
    """
    Rewrite asset paths in app.js for production deployment.
    
    Local dev paths:          Production paths:
    ../unified_db/data/...    data/...
    ../unified_db/            (empty - relative to root)
    ../public/audio/          audio/
    """
    app_js = dist_dir / "app.js"
    if not app_js.exists():
        print("[WARN] app.js not found in dist/")
        return

    print("[REWRITE] Asset paths in app.js")
    content = app_js.read_text(encoding="utf-8")

    # Replace CONFIG values
    replacements = [
        # DATA_URL: local -> production
        (
            r"DATA_URL:\s*['\"].*?['\"]",
            "DATA_URL: 'data/cards.json'",
        ),
        # VOCAB_URL: local -> production
        (
            r"VOCAB_URL:\s*['\"].*?['\"]",
            "VOCAB_URL: 'data/cards_vocab.json'",
        ),
        # LESSONS_URL: local -> production
        (
            r"LESSONS_URL:\s*['\"].*?['\"]",
            "LESSONS_URL: 'data/lessons.json'",
        ),
        # VOCAB_AUDIO_MAP_URL: local -> production
        (
            r"VOCAB_AUDIO_MAP_URL:\s*['\"].*?['\"]",
            "VOCAB_AUDIO_MAP_URL: 'data/vocab_audio_map.json'",
        ),
        # CARDS_BASE_PATH: local -> production (empty = relative to root)
        (
            r"CARDS_BASE_PATH:\s*['\"].*?['\"]",
            "CARDS_BASE_PATH: ''",
        ),
        # AUDIO_BASE_PATH: local -> production
        (
            r"AUDIO_BASE_PATH:\s*['\"].*?['\"]",
            "AUDIO_BASE_PATH: ''",
        ),
    ]

    for pattern, replacement in replacements:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            print(f"   {replacement}")
        content = new_content

    app_js.write_text(content, encoding="utf-8")


def create_headers(dist_dir: Path) -> None:
    """Create _headers file for Cloudflare Pages caching."""
    print("[CREATE] _headers (Cloudflare Pages cache config)")
    headers_content = """\
# Cloudflare Pages Headers
# https://developers.cloudflare.com/pages/configuration/headers/

# HTML — no cache (always fresh)
/*.html
  Cache-Control: public, max-age=0, must-revalidate

/
  Cache-Control: public, max-age=0, must-revalidate

# CSS & JS — cache 1 day
/*.css
  Cache-Control: public, max-age=86400, stale-while-revalidate=3600

/*.js
  Cache-Control: public, max-age=86400, stale-while-revalidate=3600

# Images — cache 30 days (they don't change)
/cards/*
  Cache-Control: public, max-age=2592000, immutable

# Audio — cache 30 days
/audio/*
  Cache-Control: public, max-age=2592000, immutable

# Data — cache 1 hour
/data/*
  Cache-Control: public, max-age=3600, stale-while-revalidate=600

# Security headers for all pages
/*
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
"""
    (dist_dir / "_headers").write_text(headers_content, encoding="utf-8")


def create_redirects(dist_dir: Path) -> None:
    """Create _redirects for Cloudflare Pages."""
    print("[CREATE] _redirects")
    redirects_content = """\
# Redirect root to index.html (usually automatic, but explicit is better)
# /src/index.html  /  301
"""
    (dist_dir / "_redirects").write_text(redirects_content, encoding="utf-8")


def print_summary(dist_dir: Path) -> None:
    """Print build summary."""
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

    print(f"\n{'='*50}")
    print(f"[BUILD COMPLETE]")
    print(f"   Output:      {dist_dir.resolve()}")
    print(f"   Total files:  {total_files}")
    print(f"   Total size:   {total_size / (1024*1024):.1f} MB")
    print(f"\n   File types:")
    for ext, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"     {ext:8s}: {count}")
    print(f"\n[DEPLOY] Run one of:")
    print(f"   npx wrangler pages deploy {dist_dir}")
    print(f"   or push to git -> Cloudflare Pages auto-deploy")
    print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(description="Build dist/ for Cloudflare Pages")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("dist"),
        help="Output directory (default: dist)",
    )
    parser.add_argument(
        "--src",
        type=Path,
        default=Path("src"),
        help="Source web app directory",
    )
    parser.add_argument(
        "--cards-dir",
        type=Path,
        default=Path("unified_db/cards"),
        help="Card images directory",
    )
    parser.add_argument(
        "--audio-dir",
        type=Path,
        default=Path("public/audio"),
        help="Audio files directory",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("public/data/cards.json"),
        help="Cards manifest JSON",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("Cardlish Learn — Build for Cloudflare Pages")
    print("=" * 50)

    clean_dist(args.output)
    copy_web_app(args.src, args.output)
    copy_cards(args.cards_dir, args.output)
    copy_audio(args.audio_dir, args.output)
    copy_data(args.data, args.output)
    rewrite_paths(args.output)
    create_headers(args.output)
    create_redirects(args.output)
    print_summary(args.output)


if __name__ == "__main__":
    main()
