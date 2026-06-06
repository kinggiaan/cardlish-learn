#!/usr/bin/env python3
"""
Generate MP3 audio files for vocabulary words and example sentences.

Uses edge-tts (Microsoft Edge TTS — free, no API key needed).
Optimized for elementary school students: slower rate, clear child-friendly voice.

Usage:
    pip install edge-tts
    python scripts/generate_vocab_audio.py
"""

import asyncio
import json
import hashlib
import os
import re
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Configuration ────────────────────────────────────────────
VOCAB_JSON = os.path.join(os.path.dirname(__file__), '..', 'public', 'data', 'cards_vocab.json')
OUTPUT_VOCAB_DIR = os.path.join(os.path.dirname(__file__), '..', 'public', 'audio', 'vocab')
OUTPUT_SENTENCE_DIR = os.path.join(os.path.dirname(__file__), '..', 'public', 'audio', 'sentences')
AUDIO_MAP_PATH = os.path.join(os.path.dirname(__file__), '..', 'public', 'data', 'vocab_audio_map.json')

# Child-friendly voice settings
# en-US-AnaNeural: Young female voice, cheerful and clear (great for kids)
# Alternatives: en-US-JennyNeural, en-US-AriaNeural
VOICE = "en-US-AnaNeural"
WORD_RATE = "-20%"      # Slower for clear phonics
SENTENCE_RATE = "-15%"  # Slightly faster for sentences
PITCH = "+5Hz"          # Slightly higher, child-friendly pitch


def strip_html(text: str) -> str:
    """Remove HTML tags (like <b>) from text."""
    return re.sub(r'<[^>]+>', '', text)


def safe_filename(word: str) -> str:
    """Convert a word to a safe filename."""
    # Lowercase, replace spaces with underscores, remove non-alphanumeric
    name = word.lower().strip()
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^a-z0-9_\-]', '', name)
    return name


def sentence_hash(text: str) -> str:
    """Create a short hash for a sentence to use as filename."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:12]


async def generate_audio(text: str, output_path: str, rate: str = WORD_RATE, pitch: str = PITCH):
    """Generate MP3 audio file using edge-tts."""
    import edge_tts

    communicate = edge_tts.Communicate(
        text=text,
        voice=VOICE,
        rate=rate,
        pitch=pitch,
    )
    await communicate.save(output_path)


async def main():
    # Ensure output directories exist
    os.makedirs(OUTPUT_VOCAB_DIR, exist_ok=True)
    os.makedirs(OUTPUT_SENTENCE_DIR, exist_ok=True)

    # Load vocabulary data
    with open(VOCAB_JSON, 'r', encoding='utf-8') as f:
        vocab = json.load(f)

    # Track mappings
    word_map = {}      # word -> relative audio path
    sentence_map = {}  # plain text -> relative audio path

    # Collect all unique words and sentences
    words_to_generate = {}   # word_lower -> word_original
    sentences_to_generate = {}  # plain_text -> hash

    for pair_id, data in vocab.items():
        # Collect words from front and back
        for side in ['front', 'back']:
            for word_obj in data.get(side, []):
                word = word_obj.get('word', '').strip()
                if word:
                    words_to_generate[word.lower()] = word

        # Collect sentences from front_sentences and back_sentences
        for side in ['front_sentences', 'back_sentences']:
            for sentence_obj in data.get(side, []):
                en_text = sentence_obj.get('en', '').strip()
                if en_text:
                    plain = strip_html(en_text)
                    if plain:
                        sentences_to_generate[plain] = sentence_hash(plain)

    # ── Generate word audio ──────────────────────────────────
    total_words = len(words_to_generate)
    print(f"\n📝 Generating audio for {total_words} unique words...")
    
    generated_words = 0
    skipped_words = 0

    for idx, (word_lower, word_original) in enumerate(sorted(words_to_generate.items()), 1):
        filename = f"{safe_filename(word_lower)}.mp3"
        output_path = os.path.join(OUTPUT_VOCAB_DIR, filename)
        relative_path = f"audio/vocab/{filename}"

        word_map[word_lower] = relative_path

        if os.path.exists(output_path):
            skipped_words += 1
            continue

        try:
            print(f"  [{idx}/{total_words}] 🔊 {word_original}")
            await generate_audio(word_original, output_path, rate=WORD_RATE)
            generated_words += 1
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"  ❌ Error generating '{word_original}': {e}")

    print(f"  ✅ Words: {generated_words} generated, {skipped_words} skipped (already exist)")

    # ── Generate sentence audio ──────────────────────────────
    total_sentences = len(sentences_to_generate)
    print(f"\n📝 Generating audio for {total_sentences} unique sentences...")
    
    generated_sentences = 0
    skipped_sentences = 0

    for idx, (plain_text, hash_name) in enumerate(sorted(sentences_to_generate.items()), 1):
        filename = f"{hash_name}.mp3"
        output_path = os.path.join(OUTPUT_SENTENCE_DIR, filename)
        relative_path = f"audio/sentences/{filename}"

        sentence_map[plain_text] = relative_path

        if os.path.exists(output_path):
            skipped_sentences += 1
            continue

        try:
            short_preview = plain_text[:60] + ('...' if len(plain_text) > 60 else '')
            print(f"  [{idx}/{total_sentences}] 🔊 {short_preview}")
            await generate_audio(plain_text, output_path, rate=SENTENCE_RATE)
            generated_sentences += 1
            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"  ❌ Error generating sentence: {e}")

    print(f"  ✅ Sentences: {generated_sentences} generated, {skipped_sentences} skipped (already exist)")

    # ── Save audio map ───────────────────────────────────────
    audio_map = {
        "words": word_map,
        "sentences": sentence_map,
    }

    with open(AUDIO_MAP_PATH, 'w', encoding='utf-8') as f:
        json.dump(audio_map, f, ensure_ascii=False, indent=2)

    print(f"\n📄 Audio map saved to: {AUDIO_MAP_PATH}")
    print(f"   {len(word_map)} word entries, {len(sentence_map)} sentence entries")
    print(f"\n🎉 Done!")


if __name__ == '__main__':
    asyncio.run(main())
