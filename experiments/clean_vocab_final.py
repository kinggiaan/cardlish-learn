import json
import re
import sys
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# ── Noise detection ──────────────────────────────────────────
# Vietnamese notes / OCR noise substrings — if ANY appears inside a word, skip it
NOISE_SUBSTRINGS = [
    "cuoi", "saudo", "ratnhe", "nhu(", "dudc", "theosau", "cacam",
    "nguyenam", "vecuoi", "cecuoi", "vunop", "tihoacc", "phanlonmot",
    "tietdo", "tiettrl", "arkhivi", "khiwh", "dauan", "camu", "phuam",
    "phatam", "dugcphat", "uqcphat", "uacphat", "udcphat", "hoacew",
    "chuy", "chua", "facuoi", "vanpham", "vaphua", "vanhe", "trongam",
    "refugeand", "averypresent", "godisour", "khivietsau", "khongphai",
    "vidu:", "vd:", "ifear", "ifaz", "idaivl", "idavl", "idall",
    "idraml", "idraemal", "idragl", "idraivl", "idoull", "idi'vaidl",
    "tgaml", "tglaidl", "tgroupl", "tepall", "teitil", "toustl",
    "tpi:", "tprezant", "tni:", "tja:", "tli", "wo.ri", "zinb",
    "zood", "leisl", "lateh", "y+phu", "y_e", "z,zz", "ivavell",
    "www.card", "wwww.card", "cardlish", "thant",
    "phai",  # Vietnamese "phải" 
]

# Exact words to always remove (OCR garbage)
NOISE_EXACT = {
    "ip", "p", "premiumoiter", "docla(o", "le'pra.ksamet", "a:dm",
    "lepll", "iraepl", "isanl", "iganl", "igall", "inall", "iraml",
    "igeiml", "igreidl", "politell", "lfairl", "ispaitl", "faivl",
    "lsoupl", "lroustl", "inoutl", "ifounl", "lloupl", "louldl",
    "lroull", "laurl", "laull", "lavll", "ljaull", "lhoacll", "inell",
    "inaifl", "lreinl", "iveinl", "fraizl", "lrouzl", "irabl", "lroudl",
    "lfraunl", "inirl", "jjirl", "itfirl", "ivirl", "despairl", "imearl",
    "lfaivl", "itfaildl", "lrestl", "poull", "scull",
    "khiu+phuamvaket", "khongphailatrongam",
    "z,zz,zecui",
}

# IPA-like patterns: start with i/l/t + consonant clusters + ending in l
IPA_NOISE_REGEX = re.compile(r'^[ilt][a-z]*[bcdfghjkmnpqrstvwxyz]l$')


def is_noise(word):
    """Return True if word is OCR noise."""
    w = word.lower().strip()
    
    # Exact match
    if w in NOISE_EXACT:
        return True
    
    # Contains Vietnamese/noise substring
    for sub in NOISE_SUBSTRINGS:
        if sub in w:
            return True
    
    # Contains special chars that don't belong in English words
    if ':' in w:
        return True
    if "'" in w and '.' in w:
        return True
    if '(' in w or ')' in w or '[' in w or ']' in w:
        return True
    if ',' in w:
        return True
    if '_' in w or '+' in w:
        return True
    
    return False


# ── Word corrections ─────────────────────────────────────────
# {(pid, side, bad_word): (correct_word, correct_ipa)}
WORD_FIXES = {
    # Front word fixes
    ("007_card", "front", "moving"): ("van", "/væn/"),
    ("217_card", "front", "nand"): ("hand", "/hænd/"),
    ("213_d", "front", "leer"): ("deer", "/dɪər/"),
    ("219_g", "front", "inger"): ("ginger", "/dʒɪndʒər/"),
    ("047_card", "front", "np"): ("au", "/ɔː/"),
    
    # Back word fixes
    ("235_z", "back", "ap"): ("zip", "/zɪp/"),
    ("039_card", "back", "ao"): ("dog", "/dɒɡ/"),
    ("back", "back", "iz"): ("zig", "/zɪɡ/"),
    ("back", "back", "linb"): ("quill", "/kwɪl/"),
    ("back", "back", "dn"): ("up", "/ʌp/"),
    ("back", "back", "lin"): ("gull", "/ɡʌl/"),
    ("back", "back", "linu"): ("null", "/nʌl/"),
    ("back", "back", "oom"): ("zoom", "/zuːm/"),
    ("back", "back", "owi"): ("owl", "/aʊl/"),
    ("back", "back", "ind"): ("bull", "/bʊl/"),
}

# Generic fixes (any pid)
GENERIC_FIXES = {
    "chewinggum": "chewing gum",
    "hot-dog": "hot dog",
}

# Words to skip for specific IPA check
SKIP_IPA_CHECK = {"tax"}


def clean_word(word, ipa, pid, side):
    """Clean a single word. Returns (word, ipa) or None to skip."""
    w = word.strip().lower()
    
    # Check noise
    if is_noise(w):
        return None
    
    # Check specific fixes
    key = (pid, side, w)
    if key in WORD_FIXES:
        return WORD_FIXES[key]
    
    # Check generic fixes (any pid) for back words
    for bad, fix_info in WORD_FIXES.items():
        if bad[0] == "back" and bad[2] == w and side == "back":
            return fix_info
    
    # Generic text fixes
    if w in GENERIC_FIXES:
        w = GENERIC_FIXES[w]
    
    # Skip specific IPA issues
    if w in SKIP_IPA_CHECK and ipa == "/%/":
        return None
    
    # Clean up IPA formatting
    ipa = ipa.replace("<", "ʌ").replace("^", "ʌ").replace("Λ", "ʌ").replace("Tj", "j").replace("I", "ɪ")
    
    return (w, ipa)


def main():
    vocab_path = Path("public/data/cards_vocab.json")
    if not vocab_path.exists():
        print("cards_vocab.json not found.")
        return
        
    with open(vocab_path, "r", encoding="utf-8") as f:
        vocab = json.load(f)
    
    total_removed = 0
    total_fixed = 0
    
    for pid, data in vocab.items():
        for side in ["front", "back"]:
            cleaned = []
            for w in data[side]:
                result = clean_word(w["word"], w["ipa"], pid, side)
                if result is None:
                    total_removed += 1
                    continue
                word, ipa = result
                if word != w["word"].strip().lower():
                    total_fixed += 1
                cleaned.append({"word": word, "ipa": ipa})
            data[side] = cleaned
        
        # Special: add missing words
        if pid == "008_card":
            if not any(x["word"] == "trap" for x in data["front"]):
                data["front"].append({"word": "trap", "ipa": "/træp/"})
    
    with open(vocab_path, "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Cleaned vocabularies saved to {vocab_path}")
    print(f"   Removed: {total_removed} noise words")
    print(f"   Fixed:   {total_fixed} words")


if __name__ == "__main__":
    main()
