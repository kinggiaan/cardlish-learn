# 🎴 Cardlish Learn — Tách & Học Flashcard

Ứng dụng tách thẻ flashcard từ file PDF scan, tự động nhận dạng mặt trước/sau,
gắn ID bằng OCR, và hiển thị trên trình duyệt với giao diện 3D premium.

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

### 3. Xem thẻ trên trình duyệt

Khởi động web server:

```bash
python -m http.server 8000
```

Mở trình duyệt: **http://localhost:8000/dist/index.html**

---

## 📖 Hướng dẫn sử dụng

### Xử lý nhiều file PDF

Chạy lần lượt từng file — database tự động gộp:

```bash
python split_cardlish_pdf.py scan0001.pdf --out unified_db --dpi 200
python split_cardlish_pdf.py scan0002.pdf --out unified_db --dpi 200
python split_cardlish_pdf.py scan0003.pdf --out unified_db --dpi 200
```

Mỗi lần chạy:
- Thẻ mới được thêm vào database
- Thẻ trùng ID sẽ được cập nhật
- Ảnh tự động sync sang `dist/`
- Viewer tự cập nhật dữ liệu mới

### Xem lại kết quả

Sau mỗi lần xử lý, kiểm tra:

- **Contact sheet** — `unified_db/review_contact_sheet_[tên_pdf].png`
  Hiển thị tất cả thẻ vừa xử lý, dạng lưới mặt trước/mặt sau cạnh nhau.

- **Viewer** — `http://localhost:8000/dist/index.html`
  Giao diện 3D lật thẻ, thư viện, tìm kiếm, nghe audio.

### Yêu cầu về file PDF scan

- Mỗi trang chứa lưới **3×3** thẻ (tối đa 9 thẻ/trang)
- Hai trang liên tiếp là mặt trước/mặt sau của cùng bộ 9 thẻ
- Mặt trước có mã **QR code** (dùng để phân biệt mặt)
- Số thẻ thực tế có thể ít hơn 9 (ô trống sẽ tự động bỏ qua)

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
