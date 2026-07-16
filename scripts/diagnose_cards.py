"""Diagnose broken cards: 214, 218, 220, 229, 232."""
import json, os, sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

cards = json.load(open("public/data/cards.json", "r", encoding="utf-8"))
vocab = json.load(open("public/data/cards_vocab.json", "r", encoding="utf-8"))
audio_map = json.load(open("public/data/vocab_audio_map.json", "r", encoding="utf-8"))

targets = ["214", "218", "220", "229", "232"]

for c in cards:
    cn = c.get("card_no", "")
    if cn not in targets:
        continue
    pid = c["pair_id"]
    audio = c.get("audio", {})
    audio_file = "public/audio/" + pid + ".mp3"
    has_file = os.path.exists(audio_file)
    file_size = os.path.getsize(audio_file) if has_file else 0

    v = vocab.get(pid, {})
    front_words = [w["word"] for w in v.get("front", [])]
    back_words = [w["word"] for w in v.get("back", [])]
    front_sents = len(v.get("front_sentences", []))
    back_sents = len(v.get("back_sentences", []))

    # Check vocab audio
    missing_audio_words = []
    for w in front_words + back_words:
        key = w.lower()
        if key not in audio_map.get("words", {}):
            missing_audio_words.append(w)

    print(f"=== Card {cn} (pid={pid}) ===")
    print(f"  needs_review: {c.get('needs_review', False)}")
    print(f"  qr_url: {c.get('qr_url', 'NONE')}")
    print(f"  AUDIO: status={audio.get('status','NONE')} source={audio.get('source','NONE')}")
    print(f"    path={audio.get('local_path','NONE')} file_exists={has_file} size={file_size}B")
    print(f"  VOCAB: front={front_words}")
    print(f"         back={back_words}")
    print(f"  SENTENCES: front={front_sents} back={back_sents}")
    print(f"  MISSING WORD AUDIO: {missing_audio_words if missing_audio_words else 'none'}")
    print()
