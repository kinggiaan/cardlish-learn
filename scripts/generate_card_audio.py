"""
Generate card audio using edge-tts for cards that don't have audio from cardlish.com.

For each card missing audio, generates an MP3 that reads:
  - The phonics pattern name (e.g. "ob", "ock", "short o")
  - The main example words from the front of the card

Usage:
  python scripts/generate_card_audio.py              # Only missing cards
  python scripts/generate_card_audio.py --force       # Regenerate all
  python scripts/generate_card_audio.py --cards 35,36 # Specific cards
"""

import json
import sys
import asyncio
import argparse
from pathlib import Path

# Add project root to path for core imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.card_utils import parse_card_filter

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import edge_tts

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CARDS_JSON = PROJECT_ROOT / "public/data/cards.json"
VOCAB_JSON = PROJECT_ROOT / "public/data/cards_vocab.json"
AUDIO_DIR = PROJECT_ROOT / "public/audio"
VOICE = "en-US-AnaNeural"  # Child-friendly voice


def get_card_speech_text(card, vocab_entry):
    """Build speech text for a card: phonics pattern name only.
    
    Each card teaches ONE phonics pattern (e.g. 'ob', 'alk', 'au').
    The pattern name is always the first front word in the vocab data.
    We read ONLY that pattern — NOT the example vocabulary words.
    """
    slug = card.get("qr_url", "").replace("https://cardlish.com/", "").strip("/")
    
    # Get first front word = the phonics pattern name
    pattern = None
    if vocab_entry:
        for w in vocab_entry.get("front", []):
            word = w.get("word", "")
            if word and word.isalpha():
                pattern = word
                break
    
    if pattern:
        return pattern
    
    # Fallback: use slug as speech
    clean_slug = slug.replace("-", " ").replace("_", " ")
    return clean_slug


async def generate_audio(text, output_path):
    """Generate MP3 using edge-tts."""
    communicate = edge_tts.Communicate(text, VOICE, rate="-20%")
    await communicate.save(str(output_path))


async def main():
    parser = argparse.ArgumentParser(description="Generate card audio via edge-tts")
    parser.add_argument("--force", action="store_true", help="Regenerate all card audio")
    parser.add_argument("--cards", type=str, help="Comma-separated card numbers")
    args = parser.parse_args()

    cards = json.loads(CARDS_JSON.read_text(encoding="utf-8"))
    vocab = json.loads(VOCAB_JSON.read_text(encoding="utf-8"))

    print(f"[INFO] Loaded {len(cards)} cards")

    # Determine which cards need audio
    # Parse card filter (matches both '015_card' and bare '015' formats)
    all_pair_ids = [c["pair_id"] for c in cards]
    card_filter = parse_card_filter(args.cards, all_pair_ids)

    to_process = []
    skipped = 0
    already_downloaded = 0

    for card in cards:
        pid = card["pair_id"]
        audio = card.get("audio", {})
        status = audio.get("status", "")

        if card_filter:
            if pid not in card_filter:
                skipped += 1
                continue
            to_process.append(card)
        elif args.force:
            to_process.append(card)
        else:
            # Only process cards without audio
            if status == "downloaded":
                local_path = audio.get("local_path", "")
                if local_path and (AUDIO_DIR.parent / local_path).exists():
                    already_downloaded += 1
                    continue
            to_process.append(card)

    if already_downloaded:
        print(f"[SKIP] {already_downloaded} cards already have downloaded audio")
    if skipped:
        print(f"[SKIP] {skipped} cards not in filter")

    if not to_process:
        print("[DONE] No cards need audio generation.")
        return

    print(f"[RUN]  Generating audio for {len(to_process)} cards...")

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    generated = 0
    updated_cards = {c["pair_id"]: c for c in cards}

    for i, card in enumerate(to_process):
        pid = card["pair_id"]
        card_no = card.get("card_no", pid.replace("_card", ""))
        output_file = AUDIO_DIR / f"{pid}.mp3"
        
        vocab_entry = vocab.get(pid, {})
        speech_text = get_card_speech_text(card, vocab_entry)

        print(f"  [{i+1}/{len(to_process)}] {pid}: \"{speech_text}\"", end=" ", flush=True)

        try:
            await generate_audio(speech_text, output_file)
            if output_file.exists() and output_file.stat().st_size > 0:
                print(f"OK ({output_file.stat().st_size:,} bytes)")
                generated += 1
                # Update card audio metadata
                updated_cards[pid]["audio"] = {
                    "status": "downloaded",
                    "page_url": card.get("qr_url", ""),
                    "remote_url": "",
                    "local_path": f"audio/{pid}.mp3",
                    "source": "edge-tts",
                }
            else:
                print("FAILED (empty)")
        except Exception as e:
            print(f"ERROR: {e}")

    # Save updated cards.json
    result_list = [updated_cards[c["pair_id"]] for c in cards]
    with open(CARDS_JSON, "w", encoding="utf-8") as f:
        json.dump(result_list, f, ensure_ascii=False, indent=2)

    print(f"\n[DONE] Generated {generated}/{len(to_process)} card audio files")
    print(f"  Updated: {CARDS_JSON}")


if __name__ == "__main__":
    asyncio.run(main())
