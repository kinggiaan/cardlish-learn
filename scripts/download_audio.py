"""
Download audio from QR URLs for all cards.
The QR URLs (e.g. https://cardlish.com/short-a/) serve MP3 files DIRECTLY.
"""
import json
import os
import sys
import io
import time
import hashlib
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

MANIFEST = Path("public/data/cards.json")
AUDIO_DIR = Path("public/audio")
DELAY = 1.0

def download_audio(url, output_path):
    """Download audio file from QR URL."""
    r = requests.get(url, headers=HEADERS, timeout=30, stream=True)
    r.raise_for_status()
    
    content_type = r.headers.get("Content-Type", "")
    
    hasher = hashlib.md5()
    total = 0
    with open(output_path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
            hasher.update(chunk)
            total += len(chunk)
    
    return {
        "content_type": content_type,
        "size": total,
        "checksum": hasher.hexdigest(),
    }

def main():
    print("[LOAD] Loading manifest...")
    with open(MANIFEST, "r", encoding="utf-8") as f:
        cards = json.load(f)
    print(f"  Found {len(cards)} cards")
    
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    
    stats = {"ok": 0, "fail": 0, "skip": 0, "no_qr": 0}
    
    for i, card in enumerate(cards):
        pid = card.get("pair_id", "?")
        qr_url = card.get("qr_url", "")
        
        if not qr_url:
            print(f"  [{i+1:3d}] {pid:18s} -- NO QR URL")
            stats["no_qr"] += 1
            continue
        
        # Output filename
        out_file = AUDIO_DIR / f"{pid}.mp3"
        
        # Skip if already downloaded
        if out_file.exists() and out_file.stat().st_size > 100:
            audio = card.get("audio", {})
            if audio.get("status") == "downloaded":
                print(f"  [{i+1:3d}] {pid:18s} -- SKIP (already downloaded)")
                stats["skip"] += 1
                continue
        
        # Download
        try:
            result = download_audio(qr_url, out_file)
            size = result["size"]
            
            # Verify it's actually audio (MP3 starts with ID3 or 0xFF 0xFB)
            with open(out_file, "rb") as f:
                header = f.read(4)
            
            is_audio = header[:3] == b"ID3" or (header[0] == 0xFF and header[1] in (0xFB, 0xF3, 0xF2, 0xE3))
            
            if is_audio and size > 500:
                card["audio"] = {
                    "status": "downloaded",
                    "page_url": qr_url,
                    "remote_url": qr_url,
                    "local_path": f"audio/{pid}.mp3",
                    "content_type": result["content_type"],
                    "checksum": result["checksum"],
                }
                print(f"  [{i+1:3d}] {pid:18s} -- OK ({size:,} bytes)")
                stats["ok"] += 1
            else:
                # Not an audio file, maybe HTML error page
                os.remove(out_file)
                card["audio"] = {
                    "status": "missing",
                    "page_url": qr_url,
                    "error": f"Response not audio (header={header[:4].hex()}, size={size})",
                }
                print(f"  [{i+1:3d}] {pid:18s} -- NOT AUDIO (size={size})")
                stats["fail"] += 1
                
        except Exception as e:
            card["audio"] = {
                "status": "error",
                "page_url": qr_url,
                "error": str(e),
            }
            print(f"  [{i+1:3d}] {pid:18s} -- ERROR: {e}")
            stats["fail"] += 1
        
        # Rate limit
        if i < len(cards) - 1:
            time.sleep(DELAY)
    
    # Save updated manifest
    print(f"\n[SAVE] Updating manifest...")
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*50}")
    print(f"DONE!")
    print(f"  Downloaded: {stats['ok']}")
    print(f"  Skipped:    {stats['skip']}")
    print(f"  Failed:     {stats['fail']}")
    print(f"  No QR:      {stats['no_qr']}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
