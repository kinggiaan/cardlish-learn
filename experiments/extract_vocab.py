import json
import re
from pathlib import Path

def get_center(box):
    # box is list of 4 points: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    return sum(xs)/len(xs), sum(ys)/len(ys)

def clean_word(text):
    text = text.strip()
    # Remove common OCR errors/symbols at the edges
    text = re.sub(r"^[^a-zA-Z]+|[^a-zA-Z]+$", "", text)
    return text

def is_valid_word(text):
    t = text.strip()
    # Must not be empty, must not contain slash, must not be numeric
    if not t or "/" in t or t.isdigit():
        return False
    # Avoid Vietnamese card explanations
    vietnamese_keywords = ["âm", "chữ", "thường", "được", "biểu", "hiện", "bằng", "sau", "đó", "phụ", "cuối", "chú", "ý"]
    t_lower = t.lower()
    for kw in vietnamese_keywords:
        if kw in t_lower:
            return False
    # Avoid labels (usually letters with trailing hyphens like 'w-', 'd-')
    if t.endswith("-") or t.startswith("-"):
        return False
    # Avoid card numbers
    if re.match(r"^\d+$", t) or re.match(r"^\d{3}[a-zA-Z]?$", t):
        return False
    # Must contain at least one english letter
    if not re.search(r"[a-zA-Z]", t):
        return False
    return True

def is_ipa(text):
    t = text.strip()
    # IPA usually has slashes or starts/ends with slash, or has phonetic chars
    if "/" in t:
        return True
    # If it has specific phonetic chars
    phonetic_chars = ["æ", "ə", "ɒ", "ʌ", "ʃ", "ʒ", "θ", "ð", "ŋ", "ɪ", "ʊ", "ɒ", "ɔ", "ɜ"]
    for c in phonetic_chars:
        if c in t:
            return True
    return False

def extract_vocab_for_side(ocr_items):
    # Separate words and IPAs
    words = []
    ipas = []
    
    # Sort items top-to-bottom
    ocr_items = sorted(ocr_items, key=lambda x: get_center(x["box"])[1])
    
    for item in ocr_items:
        text = item["text"].strip()
        if not text:
            continue
            
        box = item["box"]
        cx, cy = get_center(box)
        
        # Calculate width and height of bbox
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        
        if is_ipa(text):
            ipas.append({"text": text, "cx": cx, "cy": cy, "box": box, "width": width, "height": height})
        elif is_valid_word(text):
            words.append({"text": text, "cx": cx, "cy": cy, "box": box, "width": width, "height": height})
            
    # Pair words with IPAs spatially
    # The IPA is directly below the word (larger cy, similar cx)
    paired = []
    used_ipas = set()
    
    for w in words:
        best_ipa = None
        min_dist = float("inf")
        
        for i, ipa in enumerate(ipas):
            if i in used_ipas:
                continue
            # IPA must be below the word (y is larger)
            # and within reasonable horizontal distance (overlapping cx)
            dy = ipa["cy"] - w["cy"]
            dx = abs(ipa["cx"] - w["cx"])
            
            # IPA is usually 15-45 pixels below the word, and horizontally aligned
            if 5 < dy < 60 and dx < 50:
                dist = dy + dx * 1.5
                if dist < min_dist:
                    min_dist = dist
                    best_ipa = i
                    
        word_clean = clean_word(w["text"])
        ipa_text = ipas[best_ipa]["text"] if best_ipa is not None else ""
        
        # Clean IPA slashes
        ipa_text = ipa_text.strip().strip("/")
        if ipa_text:
            ipa_text = f"/{ipa_text}/"
            
        paired.append({
            "word": word_clean,
            "ipa": ipa_text,
            "cy": w["cy"],
            "cx": w["cx"]
        })
        if best_ipa is not None:
            used_ipas.add(best_ipa)
            
    # Sort left-to-right, then top-to-bottom
    # We can group by row (y coordinate)
    paired_sorted = []
    if paired:
        # Sort by cy first
        paired = sorted(paired, key=lambda x: x["cy"])
        # Group into rows (items within 30px vertical of each other)
        rows = []
        current_row = [paired[0]]
        for p in paired[1:]:
            if p["cy"] - current_row[0]["cy"] < 40:
                current_row.append(p)
            else:
                rows.append(current_row)
                current_row = [p]
        rows.append(current_row)
        
        # Sort each row left-to-right
        for row in rows:
            row_sorted = sorted(row, key=lambda x: x["cx"])
            for p in row_sorted:
                paired_sorted.append({
                    "word": p["word"],
                    "ipa": p["ipa"]
                })
                
    return paired_sorted

def main():
    raw_path = Path("experiments/raw_ocr_results.json")
    if not raw_path.exists():
        print("Raw OCR results not found.")
        return
        
    with open(raw_path, "r", encoding="utf-8") as f:
        results = json.load(f)
        
    extracted = {}
    for entry in results:
        pair_id = entry["pair_id"]
        front_words = extract_vocab_for_side(entry["front_ocr"])
        back_words = extract_vocab_for_side(entry["back_ocr"])
        
        extracted[pair_id] = {
            "front": front_words,
            "back": back_words
        }
        
    out_path = Path("experiments/extracted_vocab.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(extracted, f, ensure_ascii=False, indent=2)
        
    print(f"Extracted vocabularies saved to {out_path}")
    
    # Print first 5 cards for verification
    for pid in list(extracted.keys())[:5]:
        print(f"\nCard: {pid}")
        print("  Front:", [f"{w['word']} {w['ipa']}" for w in extracted[pid]["front"]])
        print("  Back: ", [f"{w['word']} {w['ipa']}" for w in extracted[pid]["back"]])

if __name__ == "__main__":
    main()
