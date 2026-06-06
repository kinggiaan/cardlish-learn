import json

def main():
    with open("public/data/cards_vocab.json", "r", encoding="utf-8") as f:
        vocab = json.load(f)
        
    out_lines = []
    out_lines.append(f"Total cards: {len(vocab)}")
    for pid, data in vocab.items():
        front_words = [f"{w['word']} {w['ipa']}" for w in data["front"]]
        back_words = [f"{w['word']} {w['ipa']}" for w in data["back"]]
        out_lines.append(f"{pid}:")
        out_lines.append(f"  Front: {front_words}")
        out_lines.append(f"  Back:  {back_words}")
        
    with open("experiments/all_vocab.txt", "w", encoding="utf-8") as f_out:
        f_out.write("\n".join(out_lines))
    print("Done! Saved to experiments/all_vocab.txt")

if __name__ == "__main__":
    main()
