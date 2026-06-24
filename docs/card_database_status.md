# 🎴 Card Database Status Report

> Generated: 2026-06-21 | Database: 297 cards | Range: #001 - #305

---

## Tổng quan

Bộ thẻ Cardlish gồm khoảng 305 thẻ. Hiện đã scan/import được **297 thẻ** thông qua 2 phương pháp:

| Phương pháp | Số thẻ | Công cụ |
|-------------|--------|---------|
| PDF scan (3×3 grid) | 295 | `batch_split.py` / `split_cardlish_pdf.py` |
| Ảnh camera (từng thẻ) | 2 | `import_card_images.py` |

---

## ❌ Thẻ thiếu (9 thẻ — chưa scan)

| Thẻ | Ghi chú |
|-----|---------|
| #016 | Nhóm 7 thẻ liên tiếp — chưa scan PDF |
| #017 | |
| #018 | |
| #019 | |
| #020 | |
| #021 | |
| #022 | |
| #211 | Thẻ lẻ — chưa scan |
| #295 | Thẻ lẻ — chưa scan |

**Cách bổ sung**: Chụp ảnh mặt trước + mặt sau rồi chạy:
```bash
python import_card_images.py --front the_XXX_front.jpg --back the_XXX_back.jpg
```

---

## ⚠️ Lỗi OCR đã phát hiện (cần sửa)

### OCR đọc sai số (2 thẻ)

OCR đọc nhầm số thẻ trên ảnh scan:

| pair_id hiện tại | OCR đọc | Số thật (xác nhận bằng mắt) | QR URL |
|------------------|---------|------------------------------|--------|
| `680_card` | 680 | **165** | `cardlish.com/ount/` |
| `900_card` | 900 | **287** | `cardlish.com/z/` |

### OCR bỏ sót số — batch cards (7 thẻ)

OCR không đọc được card number nên hệ thống đặt tên `batchXXX_YY`:

| pair_id hiện tại | Số thật (xác nhận bằng mắt) | Nội dung thẻ | QR URL |
|------------------|------------------------------|--------------|--------|
| `batch030_B1` | **024** | âm "i" (pig, swim) | `cardlish.com/short-i/` |
| `batch031_A3` | **091** | âm "eed" (bleed, seed) | `cardlish.com/eed/` |
| `batch031_C1` | **099** | âm "ei" (leisure, neither) | `cardlish.com/long-e/` |
| `batch032_B1` | **110** | âm "ile" (file, tile) | `cardlish.com/ile/` |
| `batch032_C1` | **111** | âm "ime" (chime, grime) | `cardlish.com/ime/` |
| `batch032_C3` | **117** | âm "igh" (knight, fight) | `cardlish.com/ite/` |
| `batch033_A1` | **171** | âm "own" (down, crown) | `cardlish.com/ownn/` |

### Thẻ trùng (1 thẻ)

| pair_id | Nguồn | Hành động |
|---------|-------|-----------|
| `025` | photo_import (mới, ảnh camera) | ✅ Giữ |
| `025_card` | PDF scan (cũ) | ❌ Cần xóa |

---

## Hành động khắc phục

### Đã sẵn sàng sửa (script)

1. **Đổi tên `680_card` → `165`** — sửa card_no, pair_id, tên ảnh
2. **Đổi tên `900_card` → `287`** — sửa card_no, pair_id, tên ảnh
3. **Gán số cho 7 batch cards** — sửa card_no, pair_id, tên ảnh
4. **Xóa `025_card`** — bản trùng cũ (giữ `025` từ photo import)

> Sau khi sửa: 297 - 1 (xóa trùng) = **296 thẻ**, thiếu **9 thẻ** (#016-#022, #211, #295)

### Cần chụp bổ sung

9 thẻ còn thiếu cần chụp ảnh mặt trước + sau:
- **#016 → #022** (7 thẻ liên tiếp)
- **#211** (1 thẻ lẻ)
- **#295** (1 thẻ lẻ)

---

## Công cụ import

### Từ ảnh camera (mới)
```bash
# Import 1 thẻ
python import_card_images.py --front mat_truoc.jpg --back mat_sau.jpg

# Import batch
python import_card_images.py --dir "Card photos/"

# Menu tương tác
python cardlish.py
```

### Từ PDF scan (cũ)
```bash
python batch_split.py                    # Scan PDF mới
python batch_split.py --force            # Re-scan tất cả
```
