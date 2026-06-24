#!/usr/bin/env python3
"""
Audio downloader for Cardlish Learn MVP.

Fetches audio files from QR code URLs on cardlish.com pages.
Uses static HTML parsing (requests + BeautifulSoup).

Usage:
    python scripts/fetch_audio_from_qr.py
    python scripts/fetch_audio_from_qr.py --manifest public/data/cards.json --out public/audio --delay 1.0
    python scripts/fetch_audio_from_qr.py --manifest public/data/cards.json --out public/audio --dry-run
"""

import json
import time
import hashlib
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import requests
from bs4 import BeautifulSoup


# Common audio file extensions
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".ogg", ".webm", ".aac", ".flac"}

# Request headers to appear as a normal browser
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def find_audio_url(html: str, page_url: str) -> str | None:
    """
    Parse HTML to find an audio URL.
    
    Search strategy (in priority order):
    1. <audio src="...">
    2. <source src="..."> inside <audio>
    3. Any link ending in audio extension
    4. Audio URLs in inline <script> or JSON
    """
    soup = BeautifulSoup(html, "html.parser")

    # Strategy 1: <audio src="...">
    audio_tag = soup.find("audio", src=True)
    if audio_tag:
        src = audio_tag["src"]
        return urljoin(page_url, src)

    # Strategy 2: <source src="..."> inside <audio>
    audio_tags = soup.find_all("audio")
    for audio in audio_tags:
        source = audio.find("source", src=True)
        if source:
            src = source["src"]
            return urljoin(page_url, src)

    # Strategy 3: Any <source> tag with audio type or extension
    for source in soup.find_all("source", src=True):
        src = source["src"]
        media_type = source.get("type", "")
        if "audio" in media_type or any(src.lower().endswith(ext) for ext in AUDIO_EXTENSIONS):
            return urljoin(page_url, src)

    # Strategy 4: Links ending in audio extension
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if any(href.lower().endswith(ext) for ext in AUDIO_EXTENSIONS):
            return urljoin(page_url, href)

    # Strategy 5: Audio URLs in inline scripts
    scripts = soup.find_all("script")
    for script in scripts:
        if script.string:
            # Look for URLs with audio extensions
            urls = re.findall(
                r'["\']([^"\']*(?:' + "|".join(re.escape(ext) for ext in AUDIO_EXTENSIONS) + r')[^"\']*)["\']',
                script.string,
            )
            if urls:
                return urljoin(page_url, urls[0])

    # Strategy 6: data attributes with audio URLs
    for tag in soup.find_all(attrs={"data-audio": True}):
        return urljoin(page_url, tag["data-audio"])
    for tag in soup.find_all(attrs={"data-src": True}):
        src = tag["data-src"]
        if any(src.lower().endswith(ext) for ext in AUDIO_EXTENSIONS):
            return urljoin(page_url, src)

    return None


def fetch_page(url: str, timeout: int = 15) -> str | None:
    """Fetch a page's HTML content."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        print(f"    ⚠️  Failed to fetch page: {e}")
        return None


def download_audio(url: str, output_path: Path, timeout: int = 30) -> dict:
    """Download an audio file and return metadata."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "unknown")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        hasher = hashlib.md5()
        total_bytes = 0
        
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                hasher.update(chunk)
                total_bytes += len(chunk)

        return {
            "success": True,
            "content_type": content_type,
            "checksum": hasher.hexdigest(),
            "size_bytes": total_bytes,
        }
    except requests.RequestException as e:
        return {"success": False, "error": str(e)}


def process_card(card: dict, audio_dir: Path, dry_run: bool = False) -> dict:
    """Process a single card: fetch page, find audio, download."""
    pair_id = card["pair_id"]
    qr_url = card.get("qr_url", "")

    # Skip if already downloaded
    audio_info = card.get("audio", {})
    if audio_info.get("status") == "downloaded":
        local = audio_dir / Path(audio_info.get("local_path", "")).name
        if local.exists():
            print(f"  ⏭️  {pair_id}: already downloaded")
            return card

    if not qr_url:
        print(f"  ❌ {pair_id}: no QR URL")
        card["audio"] = {
            "status": "missing",
            "page_url": "",
            "remote_url": "",
            "local_path": "",
            "error": "No QR URL in manifest",
        }
        return card

    print(f"  🔍 {pair_id}: fetching {qr_url}")

    # Fetch QR page
    html = fetch_page(qr_url)
    if not html:
        card["audio"] = {
            "status": "error",
            "page_url": qr_url,
            "remote_url": "",
            "local_path": "",
            "error": "Failed to fetch QR page",
        }
        return card

    # Find audio URL
    audio_url = find_audio_url(html, qr_url)
    if not audio_url:
        print(f"    ❌ No audio URL found on page")
        card["audio"] = {
            "status": "missing",
            "page_url": qr_url,
            "remote_url": "",
            "local_path": "",
            "error": "No audio URL found in page HTML",
        }
        return card

    print(f"    🎵 Found audio: {audio_url}")

    if dry_run:
        print(f"    🏃 DRY RUN — skipping download")
        card["audio"] = {
            "status": "pending",
            "page_url": qr_url,
            "remote_url": audio_url,
            "local_path": "",
        }
        return card

    # Determine file extension from URL
    parsed = urlparse(audio_url)
    ext = Path(parsed.path).suffix or ".mp3"
    local_filename = f"{pair_id}{ext}"
    local_path = audio_dir / local_filename

    # Download
    result = download_audio(audio_url, local_path)

    if result["success"]:
        print(f"    ✅ Downloaded: {local_filename} ({result['size_bytes']} bytes)")
        card["audio"] = {
            "status": "downloaded",
            "page_url": qr_url,
            "remote_url": audio_url,
            "local_path": f"audio/{local_filename}",
            "content_type": result["content_type"],
            "checksum": result["checksum"],
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        }
    else:
        print(f"    ❌ Download failed: {result['error']}")
        card["audio"] = {
            "status": "error",
            "page_url": qr_url,
            "remote_url": audio_url,
            "local_path": "",
            "error": result["error"],
        }

    return card


def main():
    parser = argparse.ArgumentParser(description="Download audio from Cardlish QR pages")
    parser.add_argument(
        "--manifest", "-m",
        type=Path,
        default=Path("public/data/cards.json"),
        help="Path to cards.json manifest",
    )
    parser.add_argument(
        "--out", "-o",
        type=Path,
        default=Path("public/audio"),
        help="Output directory for audio files",
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=1.0,
        help="Delay in seconds between requests (rate limiting)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only find audio URLs, don't download",
    )
    parser.add_argument(
        "--retry",
        type=int,
        default=3,
        help="Number of retries per card on failure",
    )
    args = parser.parse_args()

    # Load manifest
    print(f"📥 Loading manifest from: {args.manifest}")
    with open(args.manifest, "r", encoding="utf-8") as f:
        cards = json.load(f)
    print(f"   Found {len(cards)} cards")

    # Create output directory
    args.out.mkdir(parents=True, exist_ok=True)

    # Process each card
    stats = {"downloaded": 0, "missing": 0, "error": 0, "skipped": 0}

    for i, card in enumerate(cards):
        pair_id = card.get("pair_id", "unknown")

        # Retry logic
        for attempt in range(args.retry):
            try:
                cards[i] = process_card(card, args.out, dry_run=args.dry_run)
                break
            except Exception as e:
                if attempt < args.retry - 1:
                    print(f"    🔄 Retry {attempt + 1}/{args.retry} for {pair_id}: {e}")
                    time.sleep(args.delay)
                else:
                    print(f"    💀 All retries failed for {pair_id}: {e}")
                    cards[i]["audio"] = {
                        "status": "error",
                        "page_url": card.get("qr_url", ""),
                        "error": str(e),
                    }

        # Update stats
        status = cards[i].get("audio", {}).get("status", "error")
        if status == "downloaded":
            stats["downloaded"] += 1
        elif status == "missing":
            stats["missing"] += 1
        elif status == "error":
            stats["error"] += 1
        else:
            stats["skipped"] += 1

        # Rate limit
        if i < len(cards) - 1:
            time.sleep(args.delay)

    # Save updated manifest
    print(f"\n📝 Saving updated manifest to: {args.manifest}")
    with open(args.manifest, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)

    # Summary
    print(f"\n{'='*50}")
    print(f"📊 Summary:")
    print(f"   ✅ Downloaded: {stats['downloaded']}")
    print(f"   ❌ Missing:    {stats['missing']}")
    print(f"   ⚠️  Errors:     {stats['error']}")
    print(f"   ⏭️  Skipped:    {stats['skipped']}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
