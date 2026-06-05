"""
Try fetching cardlish.com using curl-cffi (TLS fingerprint impersonation)
or fallback to simple TLS with different ciphers.
"""
import ssl
import urllib.request

URL = "https://cardlish.com/short-a/"

# Try with custom SSL context that's more permissive
ctx = ssl.create_default_context()
ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(URL, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "identity",
})

print(f"Fetching: {URL}")
try:
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")
        print(f"Status: {resp.status}")
        print(f"Headers: {dict(resp.headers)}")
        print(f"HTML length: {len(html)}")
        
        # Save full HTML for inspection
        with open("scripts/_cardlish_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Saved full HTML to scripts/_cardlish_page.html")
        
        # Search for audio-related content
        import re
        audio_patterns = [
            r'<audio[^>]*>.*?</audio>',
            r'<source[^>]*src=["\']([^"\']+)["\']',
            r'\.mp3["\']',
            r'\.m4a["\']',
            r'\.wav["\']',
            r'\.ogg["\']',
            r'audio',
            r'sound',
            r'play',
        ]
        print("\nAudio-related findings:")
        for p in audio_patterns:
            matches = re.findall(p, html, re.IGNORECASE | re.DOTALL)
            if matches:
                for m in matches[:5]:
                    snippet = m[:200] if isinstance(m, str) else str(m)[:200]
                    try:
                        print(f"  [{p[:20]}] {snippet}")
                    except:
                        pass
                        
except Exception as e:
    print(f"Error: {e}")
    print(f"Type: {type(e).__name__}")
