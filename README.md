# 🎴 Cardlish Learn — Tách & Học Flashcard

Ứng dụng tách thẻ flashcard từ file PDF scan, tự động nhận dạng mặt trước/sau, gắn ID bằng OCR, và hiển thị trên trình duyệt với giao diện 3D premium.

## 🔗 Liên kết ứng dụng (Web Links)
*   🎓 **Trang học flashcard (Học sinh/Người dùng):**
    *   **Bản Live (Production):** [https://cardlish-learn.pages.dev/src/](https://cardlish-learn.pages.dev/src/)
    *   **Bản Thử nghiệm (Dev):** [https://dev.cardlish-learn.pages.dev/src/](https://dev.cardlish-learn.pages.dev/src/)
*   🔍 **Trang xem & duyệt kho thẻ (Dành cho Developer/Kiểm tra OCR):**
    *   **Bản Live (Production):** [https://cardlish-learn.pages.dev/unified_db/viewer/index.html](https://cardlish-learn.pages.dev/unified_db/viewer/index.html)
    *   **Bản Thử nghiệm (Dev):** [https://dev.cardlish-learn.pages.dev/unified_db/viewer/index.html](https://dev.cardlish-learn.pages.dev/unified_db/viewer/index.html)

---

## 📁 Cấu trúc dự án

```text
cardlish-learn/
  docs/                 # Tài liệu dự án
  experiments/          # Scripts thử nghiệm, debug
  src/                  # Source code web app (HTML/CSS/JS)
  core/                 # Python modules pipeline xử lý PDF
  scripts/              # Scripts production (build, manifest, audio)
  public/               # Assets runtime (audio, manifest)
    audio/              # MP3 files
    data/cards.json     # Web-ready manifest
  unified_db/           # Database ảnh thẻ (cards/ + data/)
  dist/                 # Build output cho Cloudflare (gitignored)
```

---

## 🚀 Bắt đầu nhanh

### 1. Cài đặt (chỉ cần làm 1 lần)

```bash
# Tạo môi trường ảo
python -m venv .venv

# Kích hoạt (Windows)
.venv\Scripts\activate

# Cài thư viện
pip install -r requirements.txt
```

### 2. Xử lý file PDF scan

Đặt các file PDF scan vào thư mục `Card scan/`, rồi chạy batch:

```bash
# Xử lý tất cả scan mới (tự bỏ qua scan đã xử lý)
python batch_split.py

# Xử lý lại toàn bộ từ đầu
python batch_split.py --force

# Tùy chỉnh DPI
python batch_split.py --dpi 300
```

Hoặc xử lý từng file riêng lẻ:

```bash
python split_cardlish_pdf.py "Card scan/scan0001.pdf" --out unified_db --dpi 200
```

**Tham số batch_split.py:**

| Tham số | Mô tả | Mặc định |
|---------|--------|----------|
| `--scan-dir` | Thư mục chứa file PDF scan | `Card scan` |
| `--out` | Thư mục lưu database ảnh | `unified_db` |
| `--dpi` | Độ phân giải render PDF | `200` |
| `--force` | Xử lý lại toàn bộ | `false` |

### 3. Build & Deploy

```bash
# Validate source files (check nothing is missing)
python scripts/build_deploy.py --validate

# Build dist/ for production
python scripts/build_deploy.py -o dist

# Build + auto-deploy to Cloudflare Pages
python scripts/build_deploy.py --deploy
```

Mở trên trình duyệt local: `python -m http.server 8000 -d dist` → **http://localhost:8000**

#### Build script features:

| Feature | Mô tả |
|---------|--------|
| **Pre-build validation** | Kiểm tra source files, audio subdirectories, cards.json format |
| **Post-build validation** | Xác nhận dist/ có đầy đủ audio/vocab/, audio/sentences/, đúng cards.json |
| **Auto cache-bust** | Tự tạo hash từ file content → `styles.css?v=d1a36a2b` |
| **Audio breakdown** | Hiển thị số lượng card/vocab/sentence audio riêng biệt |
| **Guard rails** | Chặn build nếu cards.json sai format (audio.status='pending') |

#### Deploy lên Cloudflare Pages

> ⚠️ **QUAN TRỌNG: Có 2 cấu trúc deploy khác nhau, KHÔNG được nhầm lẫn!**

**Cách 1: Deploy `dist/` (production)**

```bash
python scripts/build_deploy.py -o dist
npx wrangler pages deploy dist --project-name cardlish-learn
```

URL: `https://cardlish-learn.pages.dev/`

**Cách 2: Deploy `.deploy/` (branch dev)**

```bash
Copy-Item -Path src/* -Destination .deploy/src/ -Force
Copy-Item -Path public/data/* -Destination .deploy/public/data/ -Force
npx wrangler pages deploy .deploy --project-name cardlish-learn --branch dev
```

URL: `https://dev.cardlish-learn.pages.dev/src/`

> ⚠️ **Cạm bẫy đã gặp:**
> - Deploy `dist/` lên branch `dev` → URL `/src/` trỏ file cũ → **mất data mới**
> - Copy `unified_db/data/cards_manifest.json` vào `dist/data/cards.json` → **audio bị pending → im lặng hoàn toàn**
> - Build script chỉ dùng `public/data/cards.json` (source of truth, `audio.status='downloaded'`)

---

## 🎮 Tính năng Viewer

| Tính năng | Mô tả |
|-----------|-------|
| 🔄 Lật thẻ 3D | Click vào thẻ để xoay mặt trước/sau |
| ◀▶ Chuyển thẻ | Nút Trước/Sau hoặc phím ← → |
| 📚 Thư viện | Xem tất cả thẻ dạng lưới, lọc theo màu |
| 🔍 Tìm kiếm | Tìm theo số thẻ, tên, âm |
| 🔊 Nghe âm | Phát audio phát âm (nếu có) |
| 📱 Touch | Vuốt trái/phải để chuyển thẻ |
| ⌨️ Keyboard | Điều hướng bằng phím mũi tên + Enter |

---

## 📚 Tài liệu thêm

- [Developer Guide](docs/developer-guide.md) — Hướng dẫn kỹ thuật chi tiết
- [Lessons Learned](docs/lessons-learned.md) — Ghi chú lỗi thực tế đã gặp
- [MVP Roadmap](docs/roadmap-mvp.md) — Plan phát triển MVP
- [Repo Review Plan](docs/repo-review-plan.md) — Review & chuẩn hóa repo
- [Structure](docs/structure.md) — Mô tả cấu trúc thư mục

---

## ❓ Câu hỏi thường gặp

**Q: Thẻ bị nhận nhầm mặt trước/sau?**
A: Kiểm tra file PDF — mặt có QR code sẽ được đánh dấu là mặt trước.
Nếu cả hai mặt đều có hoặc không có QR, thẻ sẽ được đánh dấu "cần review".

**Q: OCR không đọc được số thẻ?**
A: Thẻ sẽ được đặt tên fallback `batch[số]_[ô]` và đánh dấu review.
Bạn có thể đổi tên file ảnh thủ công trong `unified_db/cards/`.

**Q: File scan có ít hơn 9 thẻ/trang?**
A: Hệ thống tự phát hiện ô trống (nền trắng) và bỏ qua.

**Q: Muốn xử lý lại 1 file PDF?**
A: Chạy lại lệnh — thẻ trùng ID sẽ bị ghi đè bằng kết quả mới.
