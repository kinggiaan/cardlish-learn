#!/usr/bin/env python3
"""
Analyze dominant colors of card images for Cardlish Learn.

Extracts the dominant color from each card's front image and categorizes
it into a named color group for filtering in the web UI.

Usage:
    python scripts/analyze_card_colors.py
    python scripts/analyze_card_colors.py --manifest public/data/cards.json --cards-dir unified_db
"""

import sys
import io

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import json
import argparse
import colorsys
from pathlib import Path
from collections import Counter

from PIL import Image


# Named color groups with HSL ranges
COLOR_GROUPS = {
    "red":    {"label": "Do",     "emoji": "🔴", "hex": "#ef4444", "hue_range": [(345, 360), (0, 15)]},
    "orange": {"label": "Cam",    "emoji": "🟠", "hex": "#f97316", "hue_range": [(15, 45)]},
    "yellow": {"label": "Vàng",  "emoji": "🟡", "hex": "#eab308", "hue_range": [(45, 70)]},
    "green":  {"label": "Xanh lá","emoji": "🟢", "hex": "#22c55e", "hue_range": [(70, 165)]},
    "cyan":   {"label": "Xanh lơ","emoji": "🩵", "hex": "#06b6d4", "hue_range": [(165, 200)]},
    "blue":   {"label": "Xanh",  "emoji": "🔵", "hex": "#3b82f6", "hue_range": [(200, 260)]},
    "purple": {"label": "Tím",   "emoji": "🟣", "hex": "#a855f7", "hue_range": [(260, 310)]},
    "pink":   {"label": "Hồng", "emoji": "🩷", "hex": "#ec4899", "hue_range": [(310, 345)]},
    "white":  {"label": "Trắng","emoji": "⚪", "hex": "#f1f5f9", "hue_range": []},
    "gray":   {"label": "Xám",  "emoji": "⚫", "hex": "#6b7280", "hue_range": []},
}


def get_dominant_color(image_path: Path, sample_size: int = 100) -> tuple:
    """
    Extract the dominant color from a card image.
    
    Strategy:
    - Sample border/edge regions where card color is most visible
    - Use the center band for the main content area analysis
    - K-means-like approach using quantization
    """
    try:
        img = Image.open(image_path).convert("RGB")
    except Exception as e:
        print(f"    [WARN] Cannot open {image_path}: {e}")
        return None

    w, h = img.size
    
    # Sample from border regions (top, bottom, left, right edges)
    # These areas typically show the card's background/border color
    border_pixels = []
    
    # Top edge (10% of height)
    top_h = max(1, h // 10)
    for x in range(0, w, max(1, w // sample_size)):
        for y in range(0, top_h, max(1, top_h // 3)):
            border_pixels.append(img.getpixel((min(x, w-1), min(y, h-1))))
    
    # Bottom edge
    for x in range(0, w, max(1, w // sample_size)):
        for y in range(h - top_h, h, max(1, top_h // 3)):
            border_pixels.append(img.getpixel((min(x, w-1), min(y, h-1))))
    
    # Left edge (10% of width)
    left_w = max(1, w // 10)
    for y in range(0, h, max(1, h // sample_size)):
        for x in range(0, left_w, max(1, left_w // 3)):
            border_pixels.append(img.getpixel((min(x, w-1), min(y, h-1))))
    
    # Right edge
    for y in range(0, h, max(1, h // sample_size)):
        for x in range(w - left_w, w, max(1, left_w // 3)):
            border_pixels.append(img.getpixel((min(x, w-1), min(y, h-1))))

    if not border_pixels:
        return None

    # Quantize colors to reduce noise (group similar colors)
    quantized = []
    for r, g, b in border_pixels:
        # Round to nearest 16 to group similar colors
        qr = (r // 24) * 24
        qg = (g // 24) * 24
        qb = (b // 24) * 24
        quantized.append((qr, qg, qb))
    
    # Find most common quantized color
    counter = Counter(quantized)
    
    # Filter out near-white and near-black (likely scan background)
    filtered = {}
    for color, count in counter.items():
        r, g, b = color
        brightness = (r + g + b) / 3
        # Skip very white (scan background) or very dark
        if brightness > 230:  # near white
            continue
        if brightness < 30:   # near black
            continue
        # Skip very gray (low saturation)
        max_c = max(r, g, b)
        min_c = min(r, g, b)
        if max_c - min_c < 25 and brightness > 80:  # gray
            continue
        filtered[color] = count
    
    if not filtered:
        # All colors are neutral — use most common overall
        most_common = counter.most_common(1)[0][0]
        r, g, b = most_common
        brightness = (r + g + b) / 3
        if brightness > 200:
            return ("white", (r, g, b))
        else:
            return ("gray", (r, g, b))
    
    dominant = max(filtered, key=filtered.get)
    return classify_color(dominant)


def classify_color(rgb: tuple) -> tuple:
    """Classify an RGB color into a named color group."""
    r, g, b = rgb
    
    # Convert to HSL
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    hue = h * 360
    sat = s
    light = l
    
    # Low saturation → white or gray
    if sat < 0.15:
        if light > 0.7:
            return ("white", rgb)
        else:
            return ("gray", rgb)
    
    # Very light with low-ish saturation → white
    if light > 0.85 and sat < 0.3:
        return ("white", rgb)
    
    # Classify by hue
    for group_name, group in COLOR_GROUPS.items():
        if group_name in ("white", "gray"):
            continue
        for hue_min, hue_max in group["hue_range"]:
            if hue_min <= hue < hue_max:
                return (group_name, rgb)
    
    # Fallback
    return ("gray", rgb)


def rgb_to_hex(rgb: tuple) -> str:
    """Convert RGB tuple to hex string."""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def analyze_cards(manifest_path: Path, cards_dir: Path) -> None:
    """Analyze all card images and update manifest with color info."""
    print(f"[LOAD] Loading manifest from: {manifest_path}")
    with open(manifest_path, "r", encoding="utf-8") as f:
        cards = json.load(f)
    print(f"   Found {len(cards)} cards")
    
    color_stats = Counter()
    
    print("[ANALYZE] Analyzing card colors...")
    for i, card in enumerate(cards):
        pair_id = card.get("pair_id", "unknown")
        front_image = card.get("front_image", "")
        
        if not front_image:
            card["color"] = {"group": "gray", "hex": "#6b7280", "rgb": [128, 128, 128]}
            color_stats["gray"] += 1
            continue
        
        image_path = cards_dir / front_image
        if not image_path.exists():
            print(f"  [SKIP] {pair_id}: image not found at {image_path}")
            card["color"] = {"group": "gray", "hex": "#6b7280", "rgb": [128, 128, 128]}
            color_stats["gray"] += 1
            continue
        
        # Override for consonant cards (card numbers 200-299 are gray)
        card_no = card.get("card_no", "")
        is_consonant = False
        try:
            if card_no and 200 <= int(card_no) < 300:
                is_consonant = True
        except ValueError:
            pass

        if is_consonant:
            card["color"] = {
                "group": "gray",
                "hex": "#6b7280",
                "rgb": [107, 114, 128]
            }
            color_stats["gray"] += 1
            print(f"  [{i+1:3d}/{len(cards)}] {pair_id}: gray (consonant override)")
            continue
        
        result = get_dominant_color(image_path)
        if result is None:
            card["color"] = {"group": "gray", "hex": "#6b7280", "rgb": [128, 128, 128]}
            color_stats["gray"] += 1
        else:
            group_name, rgb = result
            card["color"] = {
                "group": group_name,
                "hex": rgb_to_hex(rgb),
                "rgb": list(rgb),
            }
            color_stats[group_name] += 1
        
        print(f"  [{i+1:3d}/{len(cards)}] {pair_id}: {card['color']['group']} ({card['color']['hex']})")
    
    # Save updated manifest
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)
    
    print(f"\n[DONE] Updated manifest with color data")
    print(f"\n[STATS] Color distribution:")
    for color, count in color_stats.most_common():
        group = COLOR_GROUPS.get(color, {})
        label = group.get("label", color)
        print(f"   {label:10s}: {count:3d} cards")


def main():
    parser = argparse.ArgumentParser(description="Analyze dominant colors of card images")
    parser.add_argument(
        "--manifest", "-m",
        type=Path,
        default=Path("public/data/cards.json"),
        help="Path to cards.json manifest",
    )
    parser.add_argument(
        "--cards-dir", "-c",
        type=Path,
        default=Path("unified_db"),
        help="Base directory containing card images",
    )
    args = parser.parse_args()
    analyze_cards(args.manifest, args.cards_dir)


if __name__ == "__main__":
    main()
