import json
import os
from pathlib import Path
from rapidocr_onnxruntime import RapidOCR

def main():
    manifest_path = Path("public/data/cards.json")
    cards_dir = Path("unified_db")
    
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        cards = json.load(f)

    print(f"Loaded {len(cards)} cards from manifest.")
    ocr = RapidOCR()
    
    results = []
    
    for i, card in enumerate(cards):
        pair_id = card.get("pair_id")
        front_rel = card.get("front_image")
        back_rel = card.get("back_image")
        
        front_path = cards_dir / front_rel if front_rel else None
        back_path = cards_dir / back_rel if back_rel else None
        
        print(f"[{i+1}/{len(cards)}] Processing card {pair_id}...")
        
        front_text = []
        if front_path and front_path.exists():
            res, _ = ocr(str(front_path))
            if res:
                front_text = [{"text": text, "score": float(score), "box": box} for box, text, score in res]
        else:
            print(f"  Warning: front image not found: {front_path}")
            
        back_text = []
        if back_path and back_path.exists():
            res, _ = ocr(str(back_path))
            if res:
                back_text = [{"text": text, "score": float(score), "box": box} for box, text, score in res]
        else:
            print(f"  Warning: back image not found: {back_path}")
            
        results.append({
            "pair_id": pair_id,
            "card_no": card.get("card_no"),
            "front_ocr": front_text,
            "back_ocr": back_text
        })
        
    out_path = Path("experiments/raw_ocr_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    print(f"Completed! OCR results saved to {out_path}")

if __name__ == "__main__":
    main()
