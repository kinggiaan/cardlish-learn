"""Quick check: audio status in cards.json and test QR page for audio"""
import json

with open("public/data/cards.json", "r", encoding="utf-8") as f:
    cards = json.load(f)

print(f"Total cards: {len(cards)}")
statuses = [c.get("audio", {}).get("status", "none") for c in cards]
for s in set(statuses):
    print(f"  audio.status='{s}': {statuses.count(s)} cards")

print("\nFirst 5 cards audio info:")
for c in cards[:5]:
    audio = c.get("audio", {})
    print(f"  {c['pair_id']:15s} status={audio.get('status','?'):10s} local={audio.get('local_path','(empty)'):25s} qr={c.get('qr_url','')}")

print("\nAll unique QR URLs:")
urls = sorted(set(c.get("qr_url", "") for c in cards))
for u in urls:
    count = sum(1 for c in cards if c.get("qr_url") == u)
    print(f"  [{count} cards] {u}")
