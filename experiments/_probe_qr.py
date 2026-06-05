"""
Probe a Cardlish QR page to understand how audio is embedded.
Fetches the HTML and dumps all relevant audio-related elements.
"""
import sys
import requests
from bs4 import BeautifulSoup

URL = "https://cardlish.com/short-a/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
}

print(f"Fetching: {URL}")
resp = requests.get(URL, headers=HEADERS, timeout=15)
print(f"Status: {resp.status_code}")
print(f"Content-Type: {resp.headers.get('Content-Type','?')}")
print(f"Content-Length: {len(resp.text)} chars")
print()

soup = BeautifulSoup(resp.text, "html.parser")

# 1. <audio> tags
print("=== <audio> tags ===")
for tag in soup.find_all("audio"):
    print(f"  {tag}")
print()

# 2. <source> tags
print("=== <source> tags ===")
for tag in soup.find_all("source"):
    print(f"  {tag}")
print()

# 3. Links with audio extensions
print("=== Links with audio extensions ===")
for a in soup.find_all("a", href=True):
    h = a["href"]
    if any(ext in h.lower() for ext in [".mp3", ".m4a", ".wav", ".ogg", ".webm"]):
        print(f"  {h}")
print()

# 4. Any element with data-audio or data-src
print("=== data-audio / data-src attributes ===")
for tag in soup.find_all(attrs={"data-audio": True}):
    print(f"  data-audio: {tag['data-audio']}")
for tag in soup.find_all(attrs={"data-src": True}):
    print(f"  data-src: {tag['data-src']}")
print()

# 5. Inline scripts containing audio URLs
print("=== Audio URLs in <script> tags ===")
import re
for script in soup.find_all("script"):
    if script.string:
        urls = re.findall(r'["\']([^"\']*(?:\.mp3|\.m4a|\.wav|\.ogg|\.webm)[^"\']*)["\']', script.string)
        for u in urls:
            print(f"  {u}")
        # Also look for any 'audio' keyword
        if "audio" in script.string.lower():
            # Print a snippet around 'audio'
            for m in re.finditer(r'audio', script.string, re.IGNORECASE):
                start = max(0, m.start() - 80)
                end = min(len(script.string), m.end() + 120)
                snippet = script.string[start:end].replace('\n', ' ').strip()
                print(f"  [snippet] ...{snippet}...")
print()

# 6. All media-related URLs anywhere in HTML
print("=== All URLs containing 'audio' or media extensions in full HTML ===")
all_urls = re.findall(r'https?://[^\s"\'<>]+', resp.text)
for u in all_urls:
    if any(kw in u.lower() for kw in ["audio", ".mp3", ".m4a", ".wav", ".ogg", "sound", "media"]):
        print(f"  {u}")
print()

# 7. Page title and meta
print(f"=== Page title: {soup.title.string if soup.title else '?'} ===")
print()

# 8. Dump first 3000 chars of HTML for manual inspection
print("=== First 3000 chars of HTML ===")
sys.stdout.buffer.write(resp.text[:3000].encode("utf-8", errors="replace"))
print()
