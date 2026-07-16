"""Download card audio for cards 214, 218, 220, 229, 232 from cardlish.com QR URLs."""
import json, hashlib, sys
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
CARDS_JSON = Path("public/data/cards.json")
AUDIO_DIR = Path("public/audio")
TARGETS = ["214", "218", "220", "229", "232"]

cards = json.loads(CARDS_JSON.read_text(encoding="utf-8"))

for card in cards:
    cn = card.get("card_no", "")
    if cn not in TARGETS:
        continue

    pid = card["pair_id"]
    qr_url = card.get("qr_url", "")
    out_file = AUDIO_DIR / f"{pid}.mp3"

    if not qr_url:
        print(f"[{cn}] No QR URL - skip")
        continue

    print(f"[{cn}] Downloading from {qr_url} ...", end=" ", flush=True)
    try:
        r = requests.get(qr_url, headers=HEADERS, timeout=30, stream=True)
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
        is_mp3 = header[:3] == b"ID3" or (len(header) >= 2 and header[0] == 0xFF and header[1] in (0xFB, 0xF3, 0xF2, 0xE3))

        if is_mp3 and total > 500:
            card["audio"] = {
                "status": "downloaded",
                "page_url": qr_url,
                "remote_url": qr_url,
                "local_path": f"audio/{pid}.mp3",
                "source": "cardlish",
            }
            print(f"OK ({total:,} bytes)")
        else:
            print(f"NOT MP3 (header={header.hex()}, size={total})")
    except Exception as e:
        print(f"ERROR: {e}")

with open(CARDS_JSON, "w", encoding="utf-8") as f:
    json.dump(cards, f, ensure_ascii=False, indent=2)

print("\nDone! cards.json updated.")
