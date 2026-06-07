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

Đặt file PDF scan vào thư mục gốc, rồi chạy:

```bash
python split_cardlish_pdf.py scan0001.pdf --out unified_db --dpi 200
```

**Tham số:**

| Tham số | Mô tả | Mặc định |
|---------|--------|----------|
| `pdf` | Đường dẫn file PDF scan | *(bắt buộc)* |
| `--out` | Thư mục lưu database ảnh | `cardlish_output` |
| `--dpi` | Độ phân giải render PDF | `200` |

### 3. Build & xem trên trình duyệt

```bash
# Build dist/
python scripts/build_deploy.py --output dist

# Khởi động web server
python -m http.server 8000 -d dist
```

Mở trình duyệt: **http://localhost:8000**

---

## 📖 Hướng dẫn sử dụng

### Xử lý nhiều file PDF

Chạy lần lượt từng file — database tự động gộp:

```bash
python split_cardlish_pdf.py scan0001.pdf --out unified_db --dpi 200
python split_cardlish_pdf.py scan0002.pdf --out unified_db --dpi 200
```

### Validate assets trước deploy

```bash
python scripts/validate_assets.py --manifest public/data/cards.json --cards-dir unified_db/cards --audio-dir public/audio
```

### Deploy lên Cloudflare Pages

```bash
# Build
python scripts/build_deploy.py --output dist

# Deploy (cần Wrangler CLI)
npx wrangler pages deploy dist --project-name cardlish-learn
```

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
