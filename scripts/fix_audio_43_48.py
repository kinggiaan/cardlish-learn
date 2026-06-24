"""
Fix audio for cards 043-048.
- Cards 045, 046: re-download from cardlish.com (correct QR URLs)
- Cards 043, 044, 047, 048: generate edge-tts reading ONLY the pattern name
"""
import json
import sys
import asyncio
import hashlib
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests
import edge_tts

CARDS_JSON = Path("public/data/cards.json")
AUDIO_DIR = Path("public/audio")
VOICE = "en-US-AnaNeural"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Cards with correct cardlish URLs - download from there
DOWNLOAD_FROM_CARDLISH = {
    "045": "https://cardlish.com/alk/",
    "046": "https://cardlish.com/all/",
}

# Cards without cardlish audio - generate edge-tts with ONLY pattern name
# Pattern name = the big title text on the card front
GENERATE_EDGE_TTS = {
    "043": "a",       # "a" after w sound
    "044": "al",
    "047": "au",
    "048": "aw",
}


def download_from_cardlish(card_no, url, cards_dict):
    """Download MP3 directly from cardlish.com QR URL."""
    card = cards_dict[card_no]
    pid = card["pair_id"]
    out_file = AUDIO_DIR / f"{pid}.mp3"

    print(f"  [{card_no}] Downloading from {url} ...", end=" ", flush=True)
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        r.raise_for_status()

        hasher = hashlib.md5()
        total = 0
        with open(out_file, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
                hasher.update(chunk)
                total += len(chunk)

        # Verify MP3
        with open(out_file, "rb") as f:
            header = f.read(4)
        is_mp3 = header[:3] == b"ID3" or (header[0] == 0xFF and header[1] in (0xFB, 0xF3, 0xF2, 0xE3))

        if is_mp3 and total > 500:
            card["audio"] = {
                "status": "downloaded",
                "page_url": url,
                "remote_url": url,
                "local_path": f"audio/{pid}.mp3",
                "source": "cardlish",
            }
            print(f"OK ({total:,} bytes) - cardlish audio")
        else:
            print(f"NOT MP3 (header={header.hex()}, size={total})")
    except Exception as e:
        print(f"ERROR: {e}")


async def generate_edge_tts(card_no, pattern_text, cards_dict):
    """Generate edge-tts audio reading ONLY the pattern name."""
    card = cards_dict[card_no]
    pid = card["pair_id"]
    out_file = AUDIO_DIR / f"{pid}.mp3"

    print(f"  [{card_no}] Generating pattern '{pattern_text}' ...", end=" ", flush=True)
    try:
        communicate = edge_tts.Communicate(pattern_text, VOICE, rate="-30%")
        await communicate.save(str(out_file))
        size = out_file.stat().st_size
        card["audio"] = {
            "status": "downloaded",
            "page_url": card.get("qr_url", ""),
            "remote_url": "",
            "local_path": f"audio/{pid}.mp3",
            "source": "edge-tts",
        }
        print(f"OK ({size:,} bytes) - edge-tts pattern only")
    except Exception as e:
        print(f"ERROR: {e}")


async def main():
    cards = json.loads(CARDS_JSON.read_text(encoding="utf-8"))

    # Build lookup by card_no
    cards_dict = {}
    for c in cards:
        cn = c.get("card_no", "")
        if cn in list(DOWNLOAD_FROM_CARDLISH.keys()) + list(GENERATE_EDGE_TTS.keys()):
            cards_dict[cn] = c

    print("=== Step 1: Download from cardlish.com (045, 046) ===")
    for card_no, url in DOWNLOAD_FROM_CARDLISH.items():
        download_from_cardlish(card_no, url, cards_dict)

    print("\n=== Step 2: Generate edge-tts pattern-only (043, 044, 047, 048) ===")
    for card_no, pattern in GENERATE_EDGE_TTS.items():
        await generate_edge_tts(card_no, pattern, cards_dict)

    # Save
    with open(CARDS_JSON, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)

    print("\nDone! cards.json updated.")
    print("Test at: http://localhost:8787/src/audio_debug.html")


if __name__ == "__main__":
    asyncio.run(main())
