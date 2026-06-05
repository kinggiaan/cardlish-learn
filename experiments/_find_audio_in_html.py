"""
Fetch full HTML from QR pages and search thoroughly for audio references.
The audio URL is there but maybe in WordPress shortcode, data attribute, or JS.
"""
import sys, io, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

test_urls = [
    ("001_card", "https://cardlish.com/short-a/", "9-Short-A.mp3"),
    ("233_w",    "https://cardlish.com/w/",       "43-W.mp3"),
    ("002_card", "https://cardlish.com/ab/",      "?"),
]

for pair_id, url, expected in test_urls:
    print(f"\n{'='*70}")
    print(f"Card: {pair_id} | URL: {url} | Expected: {expected}")
    print(f"{'='*70}")
    
    r = requests.get(url, headers=HEADERS, timeout=15)
    html = r.text
    print(f"Status: {r.status_code} | HTML length: {len(html)}")
    
    # Save HTML for manual inspection
    safe_name = url.replace("https://cardlish.com/", "").replace("/", "_").strip("_")
    with open(f"scripts/_page_{safe_name}.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    # Search 1: wp-content references
    wpc = re.findall(r'wp-content/uploads/[^\s"\'<>\)]+', html)
    if wpc:
        print(f"\n  [wp-content refs]:")
        for w in set(wpc):
            print(f"    {w}")
    
    # Search 2: Any audio-related tags/attributes
    for pattern_name, pattern in [
        ("audio tag",     r'<audio[^>]*>'),
        ("source tag",    r'<source[^>]*>'),
        ("wp-audio",      r'wp-audio[^"\']*'),
        ("data-src",      r'data-src=["\'][^"\']+["\']'),
        ("data-audio",    r'data-audio=["\'][^"\']+["\']'),
        ("data-url",      r'data-url=["\'][^"\']+["\']'),
        (".mp3 ref",      r'["\'][^"\']*\.mp3[^"\']*["\']'),
        (".m4a ref",      r'["\'][^"\']*\.m4a[^"\']*["\']'),
        ("audioUrl",      r'audioUrl["\s:]+["\'][^"\']+["\']'),
        ("audio_url",     r'audio_url["\s:]+["\'][^"\']+["\']'),
        ("mediaelement",  r'mediaelement[^"\']*'),
        ("mejs",          r'mejs[^"\'<>\s]*'),
        ("wp-mediaelement",r'wp-mediaelement'),
        ("attachment",    r'wp:audio[^}]*'),
    ]:
        matches = re.findall(pattern, html, re.IGNORECASE)
        if matches:
            print(f"\n  [{pattern_name}]:")
            for m in set(matches):
                print(f"    {m[:200]}")
    
    # Search 3: Look for JSON data containing URLs
    json_blocks = re.findall(r'\{[^{}]*(?:url|src|file|mp3|audio)[^{}]*\}', html, re.IGNORECASE)
    if json_blocks:
        print(f"\n  [JSON with audio keywords]:")
        for j in json_blocks[:5]:
            print(f"    {j[:300]}")
    
    # Search 4: All URLs in the page
    all_urls = re.findall(r'https?://cardlish\.com/wp-content/[^\s"\'<>\)]+', html)
    if all_urls:
        print(f"\n  [Full cardlish wp-content URLs]:")
        for u in set(all_urls):
            print(f"    {u}")

print("\n\nDone. HTML files saved to scripts/_page_*.html for inspection.")
