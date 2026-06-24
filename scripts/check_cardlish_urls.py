"""Check if cardlish.com has direct audio URLs for missing patterns."""
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Patterns that need checking - cards with wrong QR URLs
patterns_to_check = {
    "043": ["wa", "wa-words"],
    "044": ["al", "al-words", "salt"],
    "047": ["au", "au-words"],  
    "048": ["aw", "aw-words"],
    # Also check correct ones for comparison
    "045": ["alk"],
    "046": ["all"],
}

for card_no, slugs in patterns_to_check.items():
    print(f"Card {card_no}:")
    for slug in slugs:
        url = f"https://cardlish.com/{slug}/"
        try:
            r = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
            ct = r.headers.get("Content-Type", "?")
            is_audio = "audio" in ct
            print(f"  /{slug}/ -> {r.status_code} {ct} {'AUDIO!' if is_audio else ''}")
        except Exception as e:
            print(f"  /{slug}/ -> ERROR: {e}")
    print()
