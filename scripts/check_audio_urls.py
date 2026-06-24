"""Check Content-Type of cardlish QR URLs for cards 43-48."""
import requests

URLS = {
    "043": "https://cardlish.com/short-o-2/",
    "044": "https://cardlish.com/short-o-2/",
    "045": "https://cardlish.com/alk/",
    "046": "https://cardlish.com/all/",
    "047": "https://cardlish.com/short-o-2/",
    "048": "https://cardlish.com/short-o-2/",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

checked = set()
for card_no, url in URLS.items():
    if url in checked:
        print(f"  {card_no}: same as above ({url})")
        continue
    checked.add(url)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, stream=True)
        ct = r.headers.get("Content-Type", "?")
        first_bytes = r.raw.read(16)
        is_mp3 = first_bytes[:3] == b"ID3" or (len(first_bytes) >= 2 and first_bytes[0] == 0xFF and first_bytes[1] in (0xFB, 0xF3, 0xF2, 0xE3))
        print(f"  {card_no}: {url}")
        print(f"    Status: {r.status_code}, Content-Type: {ct}")
        print(f"    First bytes: {first_bytes[:8].hex()}, Is MP3: {is_mp3}")
    except Exception as e:
        print(f"  {card_no}: ERROR - {e}")
