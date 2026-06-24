"""Reset audio status for specific cards so fetch_audio_from_qr.py re-downloads them."""
import json, sys

CARDS_JSON = "public/data/cards.json"
TARGET_CARDS = ["043", "044", "045", "046", "047", "048"]

cards = json.load(open(CARDS_JSON, "r", encoding="utf-8"))
for c in cards:
    if c.get("card_no") in TARGET_CARDS:
        cn = c["card_no"]
        c["audio"] = {
            "status": "pending",
            "page_url": c.get("qr_url", ""),
            "remote_url": "",
            "local_path": "",
        }
        print(f"Reset {cn}")

with open(CARDS_JSON, "w", encoding="utf-8") as f:
    json.dump(cards, f, ensure_ascii=False, indent=2)

print("Done - now run: python scripts/fetch_audio_from_qr.py")
