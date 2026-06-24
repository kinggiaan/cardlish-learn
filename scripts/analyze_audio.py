"""Analyze audio of WORKING cards 036-042 vs BROKEN cards 043-048."""
import json, os

cards = json.load(open("public/data/cards.json", "r", encoding="utf-8"))
vocab = json.load(open("public/data/cards_vocab.json", "r", encoding="utf-8"))

print("=== WORKING CARDS (036-042) - audio from cardlish.com ===")
for c in cards:
    cn = c.get("card_no", "")
    if cn in ["036", "037", "038", "039", "040", "041", "042"]:
        pid = c["pair_id"]
        v = vocab.get(pid, {})
        front_words = [w["word"] for w in v.get("front", [])]
        pattern = front_words[0] if front_words else "?"
        slug = c.get("qr_url", "").replace("https://cardlish.com/", "").strip("/")
        sz = os.path.getsize("public/audio/" + pid + ".mp3")
        src = c["audio"]["source"]
        print(f"  {cn}: pattern='{pattern}' slug='{slug}' size={sz:,}B source={src}")

print()
print("=== BROKEN CARDS (043-048) ===")
for c in cards:
    cn = c.get("card_no", "")
    if cn in ["043", "044", "045", "046", "047", "048"]:
        pid = c["pair_id"]
        v = vocab.get(pid, {})
        front_words = [w["word"] for w in v.get("front", [])]
        pattern = front_words[0] if front_words else "?"
        slug = c.get("qr_url", "").replace("https://cardlish.com/", "").strip("/")
        sz = os.path.getsize("public/audio/" + pid + ".mp3")
        src = c["audio"]["source"]
        print(f"  {cn}: pattern='{pattern}' slug='{slug}' size={sz:,}B source={src}")
        print(f"       front_words={front_words}")

print()
print("=== Check if cardlish.com has specific URLs for broken cards ===")
# Cards 043-048 patterns vs their QR URLs
patterns_vs_urls = {
    "043": ("wa", "short-o-2"),
    "044": ("al", "short-o-2"),
    "045": ("alk", "alk"),       # correct!
    "046": ("all", "all"),       # correct!
    "047": ("au", "short-o-2"),
    "048": ("aw", "short-o-2"),
}
for cn, (pattern, slug) in patterns_vs_urls.items():
    correct = "✅" if pattern == slug else "❌ WRONG"
    print(f"  {cn}: pattern='{pattern}' qr_slug='{slug}' {correct}")
