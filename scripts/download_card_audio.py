"""
Download card audio directly from cardlish.com QR URLs.
The QR URLs return MP3 data directly (Content-Type: audio/mpeg).

Usage:
  python scripts/download_card_audio.py              # Only missing cards
  python scripts/download_card_audio.py --cards 35,42 # Specific cards  
  python scripts/download_card_audio.py --force       # Re-download all
"""

import json, sys, time, argparse
from pathlib import Path

# Add project root to path for core imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.card_utils import parse_card_filter

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CARDS_JSON = PROJECT_ROOT / "public/data/cards.json"
AUDIO_DIR = PROJECT_ROOT / "public/audio"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def main():
    parser = argparse.ArgumentParser(description="Download card audio from cardlish.com")
    parser.add_argument("--force", action="store_true", help="Re-download all")
    parser.add_argument("--cards", type=str, help="Comma-separated card numbers (e.g. 35,36,42)")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between requests (seconds)")
    args = parser.parse_args()

    cards = json.loads(CARDS_JSON.read_text(encoding="utf-8"))
    print(f"[INFO] Loaded {len(cards)} cards")

    # Parse card filter (matches both '015_card' and bare '015' formats)
    all_pair_ids = [c["pair_id"] for c in cards]
    card_filter = parse_card_filter(args.cards, all_pair_ids)

    to_process = []
    skipped = 0
    no_qr = 0

    for card in cards:
        pid = card["pair_id"]
        qr_url = card.get("qr_url", "")
        audio = card.get("audio", {})
        source = audio.get("source", "")

        if not qr_url:
            no_qr += 1
            continue

        if card_filter:
            if pid not in card_filter:
                skipped += 1
                continue
            to_process.append(card)
        elif args.force:
            to_process.append(card)
        else:
            # Skip if already downloaded from cardlish (not edge-tts)
            if audio.get("status") == "downloaded" and source != "edge-tts":
                mp3_path = AUDIO_DIR / f"{pid}.mp3"
                if mp3_path.exists():
                    skipped += 1
                    continue
            to_process.append(card)

    if skipped:
        print(f"[SKIP] {skipped} cards already have cardlish audio")
    if no_qr:
        print(f"[SKIP] {no_qr} cards have no QR URL")

    if not to_process:
        print("[DONE] No cards to download.")
        return

    print(f"[RUN]  Downloading audio for {len(to_process)} cards...")
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = 0
    updated = {c["pair_id"]: c for c in cards}

    for i, card in enumerate(to_process):
        pid = card["pair_id"]
        qr_url = card["qr_url"]
        output = AUDIO_DIR / f"{pid}.mp3"

        print(f"  [{i+1}/{len(to_process)}] {pid}: {qr_url}", end=" ", flush=True)

        try:
            r = requests.get(qr_url, headers=HEADERS, timeout=15)
            ct = r.headers.get("Content-Type", "")

            if "audio" in ct and len(r.content) > 100:
                output.write_bytes(r.content)
                print(f"OK ({len(r.content):,} bytes)")
                success += 1
                updated[pid]["audio"] = {
                    "status": "downloaded",
                    "page_url": qr_url,
                    "remote_url": qr_url,
                    "local_path": f"audio/{pid}.mp3",
                    "source": "cardlish",
                }
            else:
                print(f"SKIP (Content-Type: {ct}, size: {len(r.content)})")
                failed += 1
        except Exception as e:
            print(f"ERROR: {e}")
            failed += 1

        if args.delay > 0 and i < len(to_process) - 1:
            time.sleep(args.delay)

    # Save updated cards.json
    result = [updated[c["pair_id"]] for c in cards]
    with open(CARDS_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n[DONE] Downloaded: {success}, Failed: {failed}")
    print(f"  Updated: {CARDS_JSON}")


if __name__ == "__main__":
    main()
