"""Show vocab data for cards 43-48 to determine correct audio content."""
import json

cards = json.load(open("public/data/cards.json", "r", encoding="utf-8"))
vocab = json.load(open("public/data/cards_vocab.json", "r", encoding="utf-8"))

for c in cards:
    cn = c.get("card_no", "")
    if cn not in ["035", "036", "037", "038", "039", "040", "041", "042", "043", "044", "045", "046", "047", "048"]:
        continue
    pid = c["pair_id"]
    v = vocab.get(pid, {})
    front_words = [w["word"] for w in v.get("front", [])]
    back_words = [w["word"] for w in v.get("back", [])]
    slug = c.get("qr_url", "").replace("https://cardlish.com/", "").strip("/")
    print(f"Card {cn} (pid={pid}, slug={slug}):")
    print(f"  Front words: {front_words[:6]}")
    print(f"  Back words:  {back_words[:6]}")
    print()
