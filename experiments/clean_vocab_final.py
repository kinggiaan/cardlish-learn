import json
from pathlib import Path

def main():
    vocab_path = Path("public/data/cards_vocab.json")
    if not vocab_path.exists():
        print("cards_vocab.json not found.")
        return
        
    with open(vocab_path, "r", encoding="utf-8") as f:
        vocab = json.load(f)
        
    for pid, data in vocab.items():
        # Clean up front words
        cleaned_front = []
        for w in data["front"]:
            word = w["word"].strip().lower()
            ipa = w["ipa"].strip()
            
            # Skip Vietnamese explanations or weird noise
            if "chuy" in word or "phat" in word or "chua" in word or word == "phuamsaudo" or word == "facuoi" or word == "ip":
                continue
            if word == "moving":
                # Card 007 Front has 'van' and 'can'. OCR read 'moving' instead of 'van'
                word = "van"
                ipa = "/væn/"
            if word == "tax" and ipa == "/%/":
                continue
            if word == "nand":
                # Card 217 Front has 'hand' and 'horse'. OCR read 'nand'
                word = "hand"
                ipa = "/hænd/"
            if word == "leer":
                # Card 213 Front has 'deer' and 'dog'. OCR read 'leer'
                word = "deer"
                ipa = "/dɪər/"
            if word == "inger":
                # Card 219 Front has 'ginger'. OCR read 'inger'
                word = "ginger"
                ipa = "/dʒɪndʒər/"
                
            cleaned_front.append({"word": word, "ipa": ipa})
            
        # Add missing front words if any
        if pid == "008_card":
            # Card 008 Front has 'clap' and 'trap'. 'trap' was missing IPA, add it
            if not any(x["word"] == "trap" for x in cleaned_front):
                cleaned_front.append({"word": "trap", "ipa": "/træp/"})
                
        # Clean up back words
        cleaned_back = []
        for w in data["back"]:
            word = w["word"].strip().lower()
            ipa = w["ipa"].strip()
            
            if word in ("premiumoiter", "p"):
                continue
            if word == "iz":
                word = "zig"
                ipa = "/zɪɡ/"
            if word == "linb":
                word = "quill"
                ipa = "/kwɪl/"
            if word == "dn":
                word = "up"
                ipa = "/ʌp/"
            if word == "lin":
                word = "gull"
                ipa = "/ɡʌl/"
            if word == "linu":
                word = "null"
                ipa = "/nʌl/"
            if word == "chewinggum":
                word = "chewing gum"
            if word == "oom":
                word = "zoom"
                ipa = "/zuːm/"
            if word == "ap" and pid == "235_z":
                word = "zip"
                ipa = "/zɪp/"
            if word == "owi":
                word = "owl"
                ipa = "/aʊl/"
            if word == "ind":
                word = "bull"
                ipa = "/bʊl/"
                
            # Clean up IPA formatting (common typos)
            ipa = ipa.replace("<", "ʌ").replace("^", "ʌ").replace("Λ", "ʌ").replace("Tj", "j").replace("I", "ɪ")
            cleaned_back.append({"word": word, "ipa": ipa})
            
        data["front"] = cleaned_front
        data["back"] = cleaned_back
        
    with open(vocab_path, "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False, indent=2)
        
    print("Cleaned vocabularies saved back to public/data/cards_vocab.json")

if __name__ == "__main__":
    main()
