# 🛠️ Cardlish Learn — Developer Guide

Tài liệu kiến trúc và hướng dẫn bảo trì cho developer.

---

## Kiến trúc tổng quan & Cấu trúc thư mục

```text
cardlish_split_mvp/
├── core/                       # Mã nguồn Python cốt lõi xử lý PDF và cắt thẻ
│   ├── __init__.py
│   ├── contact_sheet.py        # Tạo ảnh lưới (contact sheet) để kiểm tra kết quả
│   ├── dist_sync.py            # Đồng bộ hóa ảnh thẻ và dữ liệu sang thư mục dist/
│   ├── grid.py                 # Thuật toán phát hiện lưới 3x3 và cắt từng ô thẻ
│   ├── html_viewer.py          # Trình tạo/hỗ trợ Viewer HTML
│   ├── manifest.py             # Đọc/ghi file manifest chứa siêu dữ liệu thẻ (JSON, CSV)
│   ├── ocr.py                  # Nhận dạng số thẻ (ID) và nhãn bằng EasyOCR
│   ├── pairing.py              # Ghép cặp mặt trước/sau dựa trên mã QR code
│   ├── pdf.py                  # Render các trang PDF scan thành file ảnh PNG độ phân giải cao
│   └── qr.py                   # Phát hiện và giải mã QR code trên mặt thẻ
│
├── scripts/                    # Các tập lệnh tiện ích và build deploy dự án
│   ├── analyze_card_colors.py  # Phân tích màu chủ đạo của thẻ để lọc trên giao diện
│   ├── build_deploy.py         # Build đóng gói toàn bộ tài nguyên vào dist/ để deploy lên Cloudflare Pages
│   ├── build_manifest.py       # Chuyển đổi manifest thô thành định dạng tối ưu cho web
│   ├── download_audio.py       # Tải file âm thanh phát âm từ các link QR
│   ├── fetch_audio_from_qr.py  # Quét QR và cào âm thanh từ trang từ điển
│   └── _*.py                   # Các script chạy thử nghiệm nội bộ (audio, qr, probe...)
│
├── src/                        # Giao diện web và logic app client (HTML/CSS/JS)
│   ├── app.js                  # Logic ứng dụng: tìm kiếm, bộ lọc màu, lật thẻ 3D, chế độ học tập
│   ├── index.html              # Giao diện HTML chuẩn SEO, tối ưu hiển thị
│   └── styles.css              # Style CSS Premium: Glassmorphism, Dark mode, hiệu ứng lật 3D
│
├── unified_db/                 # Cơ sở dữ liệu ảnh và manifest sau khi cắt (được lưu trên Git)
│   ├── cards/                  # Chứa toàn bộ ảnh mặt trước/sau của các thẻ đã xử lý
│   ├── data/                   # Manifest gốc chứa thông tin chi tiết từng thẻ (`cards_manifest.json`)
│   ├── raw_cells/              # Chứa các ảnh ô cắt thô từ các trang scan gốc
│   ├── rendered_pages/         # Chứa ảnh chụp toàn bộ trang PDF ban đầu
│   └── review_contact_sheet_*.png  # Ảnh lưới để kiểm tra nhanh chất lượng cắt
│
├── .gitignore                  # Cấu hình bỏ qua môi trường ảo (.venv), file build tạm và file scan PDF lớn
├── cardlish_mvp_plan.md        # Kế hoạch phát triển MVP ban đầu
├── lessons_learned.md          # Các bài học kinh nghiệm đúc kết được trong quá trình code
├── README.md                   # Hướng dẫn chạy nhanh ứng dụng và mô tả dự án
├── README_DEV.md               # Tài liệu chi tiết dành cho lập trình viên phát triển thêm
├── requirements.txt            # Danh sách thư viện Python cần cài đặt
├── scan0001.pdf                # File scan mẫu (1 trang) để chạy thử nghiệm pipeline
└── STRUCTURE.md                # Tài liệu cấu trúc thư mục chi tiết
```


---

## Pipeline flow

```
scan0001.pdf
     │
     ▼
┌─────────────────────────────────────────────────┐
│  Step 1: pdf.py — render_pdf()                  │
│  PDF → rendered_pages/scan0001_page_001.png     │
│         rendered_pages/scan0001_page_002.png    │
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│  Step 2: grid.py — crop_pages()                 │
│  Detect 3×3 grid → crop 9 cells per page        │
│  → raw_cells/scan0001_page_001_A1.png ... C3    │
│  Also runs QR detection on each cell            │
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│  Step 3: ocr.py — CardOCRExtractor()            │
│  Initialize RapidOCR engine                     │
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│  Step 4: pairing.py — build_pairs()             │
│  • Pair page_001 cells with page_002 cells      │
│  • QR side → front, non-QR side → back          │
│  • Skip blank cells (mean>240, std<30)          │
│  • OCR front image → extract card_no + label    │
│  • Copy images to cards/{id}_front.png          │
│  • Merge with existing database                 │
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│  Step 5: manifest.py — write_manifest()         │
│  Write unified_db/data/cards_manifest.json      │
│  Write unified_db/data/cards_manifest.csv       │
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│  Step 6: contact_sheet.py                       │
│  Generate review_contact_sheet_scan0001.png     │
│  (visual QA: front+back side-by-side per card)  │
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│  Step 7: dist_sync.py — sync_to_dist()          │
│  • Copy new/updated images → dist/cards/        │
│  • Merge manifest into dist/data/cards.json     │
│  • Preserve existing color, audio, learning     │
└─────────────────────────────────────────────────┘
```

---

## Module reference

### `core/pdf.py`

```python
render_pdf(pdf_path, out_dir, prefix, dpi=200) -> List[Path]
```

Renders each PDF page to a PNG image using PyMuPDF (fitz).
Files are named `{prefix}_page_{NNN}.png` to prevent collisions across scans.

### `core/grid.py`

```python
crop_pages(page_paths, out_dir) -> List[CropInfo]
```

For each rendered page:
1. Detects 3 column and 3 row bands using projection profile analysis
2. Falls back to fixed thirds if detection fails
3. Crops each of the 9 cells (A1..C3)
4. Runs QR detection on each crop
5. Saves crops to `raw_cells/`

**Key dataclass:**
```python
@dataclass
class CropInfo:
    page_index: int              # 1-based page number
    cell: str                    # "A1", "A2", ..., "C3"
    row: int                     # 1-3
    col: int                     # 1-3
    crop_path: str               # Relative path to crop image
    bbox_xyxy: Tuple[int,int,int,int]  # Bounding box in page coords
    qr_url: str                  # Decoded QR URL or ""
```

### `core/qr.py`

```python
decode_qr(img_bgr) -> str
```

Multi-scale QR detection using OpenCV's `QRCodeDetector`.
Tries scales 1.0, 1.5, 2.0, 3.0 on both BGR and grayscale variants.

### `core/ocr.py`

```python
class CardOCRExtractor:
    def extract_card_meta(img_path) -> Tuple[str, str]
```

Uses `rapidocr-onnxruntime` to extract:
- **card_no**: 3-digit number (regex `\b\d{3}\b`)
- **label**: Hyphenated label like `g-`, `ph-` (regex `\b([A-Za-z]+-`)

### `core/pairing.py`

```python
build_pairs(crops, out_dir, ocr_extractor, existing_pairs) -> Tuple[List[CardPair], List[CardPair]]
```

Core logic:
1. Groups crops by `(page_index, cell)`
2. Iterates page pairs (1+2, 3+4, etc.)
3. For each cell: checks QR on both sides → determines front/back
4. Skips blank cells (both sides have `mean > 240` and `std < 30`)
5. Runs OCR on front image → extracts card number and label
6. Copies images to `cards/` with OCR-based names
7. Merges with existing database (new entries overwrite by `pair_id`)

**Front/back decision matrix:**

| Page A has QR | Page B has QR | Result |
|:---:|:---:|---|
| ✅ | ❌ | A = front, B = back |
| ❌ | ✅ | B = front, A = back |
| ✅ | ✅ | A = front (flagged for review) |
| ❌ | ❌ | A = front (flagged for review) |

### `core/manifest.py`

```python
load_existing_pairs(out_dir) -> List[CardPair]
write_manifest(pairs, out_dir) -> None
```

Reads/writes `data/cards_manifest.json` and `.csv`.
All image paths use POSIX forward slashes for browser compatibility.

### `core/dist_sync.py`

```python
sync_to_dist(pairs, unified_dir, dist_dir) -> None
```

Bridges the pipeline output to the web app:
1. Copies new/modified images from `unified_db/cards/` → `dist/cards/`
   (skips unchanged files based on mtime)
2. Merges pipeline manifest into `dist/data/cards.json`:
   - Existing records: overlay pipeline fields, keep `color`, `audio`, `learning`
   - New records: create with default metadata stubs

### `core/contact_sheet.py`

```python
make_review_contact_sheet(pairs, out_dir, pdf_name) -> None
```

Generates a visual QA image showing each card's front and back side-by-side.

## Developer Review Page (Trang duyệt kho thẻ cho Dev)

Để kiểm tra nhanh và chính xác toàn bộ danh sách thẻ sau khi chạy pipeline tách thẻ (bao gồm cả các thẻ bị gắn nhãn lỗi OCR hoặc cần review):
- **Bản Live (Production):** [https://cardlish-learn.pages.dev/unified_db/viewer/index.html](https://cardlish-learn.pages.dev/unified_db/viewer/index.html)
- **Bản Thử nghiệm (Dev):** [https://dev.cardlish-learn.pages.dev/unified_db/viewer/index.html](https://dev.cardlish-learn.pages.dev/unified_db/viewer/index.html)

### Các tính năng hỗ trợ duyệt thẻ lỗi
1. **Phân loại thẻ bằng thanh Tab**:
   - **Tất cả**: Hiển thị toàn bộ thẻ đang có trong cơ sở dữ liệu.
   - **Đúng & Đủ**: Chỉ hiển thị các thẻ hợp lệ (đã được duyệt hoặc không phát hiện lỗi).
   - **Thẻ lỗi / Cần duyệt**: Gom tất cả thẻ bị thiếu số thẻ (lỗi OCR), thiếu mã QR, hoặc thẻ có ghi chú lỗi cần xem xét. Có hiển thị badge đếm số lượng lỗi màu đỏ ở đầu tab.
2. **Xét duyệt trực tiếp trên giao diện**:
   - **`✅ Duyệt`**: Nhấn vào để xác nhận thẻ đúng/đủ (xóa cảnh báo lỗi và chuyển thẻ sang nhóm hợp lệ).
   - **`⚠️ Báo lỗi`**: Đánh dấu thẻ bị lỗi và cho phép nhập ghi chú lý do lỗi qua hộp thoại nhanh.
   - Các thao tác này được lưu tự động trong trình duyệt (`localStorage`) để không bị mất khi F5 tải lại trang.
3. **Nhập/Xuất JSON sửa đổi nhanh**:
   - **Xuất JSON**: Tải xuống file JSON chứa toàn bộ dữ liệu thẻ hiện tại cùng với các cập nhật trạng thái duyệt (`needs_review`, `review_note`).
   - **Nhập JSON**: Bạn có thể sửa trực tiếp thông tin thẻ (như điền số thẻ `card_no` bị thiếu hoặc sửa `label`) trong file JSON và bấm nút **"Nhập JSON"** để tải lên. Hệ thống sẽ cập nhật đè thông tin mới vào danh sách thẻ, lưu trạng thái duyệt và làm mới giao diện ngay lập tức.

---

## dist/ web app

The `dist/` folder is a standalone **vanilla HTML/CSS/JS** web application.
No build step required — just serve with any HTTP server.

### Data format (`dist/data/cards.json`)

```jsonc
[
  {
    // Core fields (from pipeline)
    "pair_id": "216_g",
    "card_no": "216",
    "label": "g-",
    "cell": "C3",
    "qr_url": "https://cardlish.com/g/",
    "front_image": "cards/216_g_front.png",
    "back_image": "cards/216_g_back.png",
    "needs_review": false,
    "review_note": "",

    // Extended fields (app-specific, preserved during sync)
    "display_label": "216",
    "color": { "group": "green", "hex": "#a8d8a8", "rgb": [168, 216, 168] },
    "audio": { "status": "downloaded", "local_path": "audio/216_g.mp3" },
    "learning": { "day": null, "known": false, "review_count": 0 }
  }
]
```

### App features
- **Single-card 3D flip view** with swipe gestures and keyboard nav
- **Gallery mode** with search, color filters, and card count selector
- **Audio playback** from `dist/audio/` MP3 files
- **Progress tracking** with localStorage persistence
- **Responsive**: mobile, tablet, desktop, TV breakpoints
- **Pointer indicator** for TV/remote control usage

---

## Adding new features

### Adding a new pipeline step

1. Create `core/your_step.py` with a function
2. Import and call it in `split_cardlish_pdf.py` between the existing steps
3. If it modifies card data, make sure to pass updated `pairs` forward

### Adding fields to CardPair

1. Add field to `CardPair` dataclass in `core/pairing.py`
2. Update `load_existing_pairs()` in `core/manifest.py` to read the new field
3. Update `sync_to_dist()` in `core/dist_sync.py` to include it in the overlay list

### Modifying the web viewer

- Edit `dist/styles.css` for visual changes
- Edit `dist/app.js` for behavior changes
- Edit `dist/index.html` for structure changes
- No build step needed — changes are live on refresh

---

## Debugging tips

### Check raw cell crops
```bash
# View what the grid detector cropped
ls unified_db/raw_cells/
```

### Verify QR + OCR on a specific cell
```python
from core.qr import decode_qr
from core.ocr import CardOCRExtractor
import cv2

img = cv2.imread("unified_db/raw_cells/scan0001_page_002_C3.png")
print("QR:", decode_qr(img))

ocr = CardOCRExtractor()
print("OCR:", ocr.extract_card_meta("unified_db/raw_cells/scan0001_page_002_C3.png"))
```

### Re-process a single PDF
```bash
python split_cardlish_pdf.py scan0001.pdf --out unified_db --dpi 200
```
Existing cards with the same `pair_id` will be overwritten.

### Check blank cell detection
A cell is blank when both sides have `mean > 240.0` and `std < 30.0` on grayscale.
Adjust thresholds in `pairing.py` → `is_cell_blank()` if needed.
