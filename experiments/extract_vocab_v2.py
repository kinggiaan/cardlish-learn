import json
import re
from pathlib import Path

def get_center(box):
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    return sum(xs)/len(xs), sum(ys)/len(ys)

def clean_word(text):
    text = text.strip()
    # Remove non-alphabetic chars
    text = re.sub(r"^[^a-zA-Z]+|[^a-zA-Z]+$", "", text)
    return text

def is_word_candidate(text):
    t = text.strip()
    # Must not contain spaces, must not be empty, must be at least 2 chars
    if " " in t or not t or len(t) < 2:
        return False
    # Must not be all digits
    if t.isdigit():
        return False
    # Avoid card labels/numbers (like 001, 212_b, etc.)
    if re.match(r"^\d+$", t) or re.match(r"^\d{3}[a-zA-Z]?$", t):
        return False
    # Avoid labels ending or starting with hyphen
    if t.endswith("-") or t.startswith("-"):
        return False
    # Must contain english letters
    if not re.search(r"[a-zA-Z]", t):
        return False
    # Avoid Vietnamese words/explanations (common OCR parts without spaces)
    vietnamese_words = {"âm", "chữ", "thường", "được", "biểu", "hiện", "bằng", "sau", "đó", "phụ", "cuối", "chú", "ý", "phát"}
    if t.lower() in vietnamese_words:
        return False
    return True

def clean_ipa(text):
    t = text.strip()
    # Remove surrounding slashes if any
    t = t.strip("/")
    # Replace common OCR misreadings of phonetic symbols if obvious,
    # but keeping it close to original is fine. Let's just wrap in slashes.
    return f"/{t}/"

def extract_vocab_for_side(ocr_items):
    # Sort items by vertical position (top to bottom)
    items = []
    for item in ocr_items:
        text = item["text"].strip()
        if not text:
            continue
        cx, cy = get_center(item["box"])
        items.append({
            "text": text,
            "cx": cx,
            "cy": cy,
            "box": item["box"]
        })
        
    # Find word candidates
    word_candidates = []
    for item in items:
        if is_word_candidate(item["text"]):
            word_candidates.append(item)
            
    # Sort candidates by top-to-bottom
    word_candidates = sorted(word_candidates, key=lambda x: x["cy"])
    
    paired = []
    used_item_indices = set()
    
    # Map item back to index in items
    for w in word_candidates:
        w_idx = items.index(w)
        if w_idx in used_item_indices:
            continue
            
        # Search for any item directly below w
        best_ipa_item = None
        best_ipa_idx = -1
        min_dist = float("inf")
        
        for idx, item in enumerate(items):
            if idx == w_idx or idx in used_item_indices:
                continue
                
            dy = item["cy"] - w["cy"]
            dx = abs(item["cx"] - w["cx"])
            
            # IPA is directly below (dy > 5 and dy < 60) and horizontally close (dx < 50)
            if 5 < dy < 60 and dx < 50:
                dist = dy + dx * 1.5
                if dist < min_dist:
                    min_dist = dist
                    best_ipa_item = item
                    best_ipa_idx = idx
                    
        word_clean = clean_word(w["text"])
        
        if best_ipa_item:
            ipa_clean = clean_ipa(best_ipa_item["text"])
            used_item_indices.add(best_ipa_idx)
        else:
            ipa_clean = ""
            
        paired.append({
            "word": word_clean,
            "ipa": ipa_clean,
            "cy": w["cy"],
            "cx": w["cx"]
        })
        used_item_indices.add(w_idx)
        
    # Sort left-to-right, then top-to-bottom
    paired_sorted = []
    if paired:
        # Sort by cy first
        paired = sorted(paired, key=lambda x: x["cy"])
        # Group into rows (items within 40px vertical of each other)
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
        
    out_path = Path("experiments/extracted_vocab_v2.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(extracted, f, ensure_ascii=False, indent=2)
        
    print(f"Extracted vocabularies saved to {out_path}")
    
    # Print first 10 cards for verification
    for pid in list(extracted.keys())[:10]:
        print(f"\nCard: {pid}")
        print("  Front:", [f"{w['word']} {w['ipa']}" for w in extracted[pid]["front"]])
        print("  Back: ", [f"{w['word']} {w['ipa']}" for w in extracted[pid]["back"]])

if __name__ == "__main__":
    main()
