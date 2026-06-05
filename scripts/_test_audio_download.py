"""
Test downloading audio directly from the wp-content URL the user provided.
Then try to fetch a QR page to find more audio URLs.
"""
import os
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# Step 1: Try downloading the direct audio URL
audio_url = "https://cardlish.com/wp-content/uploads/2020/08/9-Short-A.mp3"
print(f"=== Step 1: Download audio directly ===")
print(f"URL: {audio_url}")

os.makedirs("public/audio", exist_ok=True)

try:
    r = requests.get(audio_url, headers=HEADERS, timeout=15, stream=True)
    print(f"Status: {r.status_code}")
    print(f"Content-Type: {r.headers.get('Content-Type', '?')}")
    print(f"Content-Length: {r.headers.get('Content-Length', '?')}")
    
    if r.status_code == 200 and "audio" in r.headers.get("Content-Type", ""):
        out = "public/audio/001_card.mp3"
        with open(out, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        size = os.path.getsize(out)
        print(f"SAVED: {out} ({size} bytes)")
    else:
        print(f"Response body preview: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

# Step 2: Try fetching a QR page to find audio URL pattern
print(f"\n=== Step 2: Fetch QR page to find audio <source> ===")
page_urls = [
    "https://cardlish.com/short-a/",
    "https://cardlish.com/ab/",
    "https://cardlish.com/b/",
]

for page_url in page_urls:
    print(f"\nFetching: {page_url}")
    try:
        r = requests.get(page_url, headers=HEADERS, timeout=15)
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            import re
            # Find all mp3 URLs in the page
            mp3s = re.findall(r'https?://[^\s"\'<>]+\.mp3', r.text)
            if mp3s:
                for mp3 in set(mp3s):
                    print(f"  FOUND MP3: {mp3}")
            else:
                print(f"  No .mp3 URLs found in HTML")
                # Check for audio tags
                audios = re.findall(r'<audio[^>]*>.*?</audio>', r.text, re.DOTALL)
                if audios:
                    for a in audios:
                        print(f"  <audio> tag: {a[:200]}")
                # Check for wp-content
                wpc = re.findall(r'wp-content/uploads/[^\s"\'<>]+', r.text)
                if wpc:
                    for w in wpc[:5]:
                        print(f"  wp-content ref: {w}")
    except Exception as e:
        print(f"  Error: {e}")
