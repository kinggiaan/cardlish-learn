import json, sys
sys.stdout.reconfigure(encoding='utf-8')

data = json.load(open('unified_db/data/cards_manifest.json', 'r', encoding='utf-8'))

fixes = {
    '680_card':    '165',  # OCR đọc "680" từ hình máy tính tiền, thực ra là 165
    '900_card':    '287',  # OCR đọc "900" từ bảng điểm game show, thực ra là 287
    'batch030_B1': '024',  # OCR miss, số bị cắt dưới cùng
}

for card in data:
    if card['pair_id'] in fixes:
        old = card['card_no']
        card['card_no'] = fixes[card['pair_id']]
        print(f"  ✅ {card['pair_id']}: '{old}' → '{fixes[card['pair_id']]}'")

json.dump(data, open('unified_db/data/cards_manifest.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

# Recount
nums = set()
for x in data:
    if x['card_no'] and x['card_no'].isdigit():
        nums.add(int(x['card_no']))
missing = sorted(set(range(306)) - nums)
print(f"\nCòn thiếu {len(missing)} thẻ: {['#'+str(n).zfill(3) for n in missing]}")

from pathlib import Path
from core.manifest import load_existing_pairs
from core.html_viewer import make_html_viewer
from core.dist_sync import sync_to_dist
p = load_existing_pairs(Path('unified_db'))
make_html_viewer(p, Path('unified_db'))
sync_to_dist(p, Path('unified_db'), Path('dist'))
print("Viewer updated!")
