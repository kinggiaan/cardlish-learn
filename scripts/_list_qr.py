import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
cards = json.load(open("unified_db/data/cards_manifest.json", "r", encoding="utf-8"))
for c in cards:
    pid = c.get("pair_id", "?")
    qr = c.get("qr_url", "")
    print(f"{pid:20s}  {qr}")

