# Cardlish Learn — Repository Structure

Dưới đây là cấu trúc thư mục chi tiết của dự án **Cardlish Learn** và chức năng của từng file/thư mục.

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
├── src/                        # Mã nguồn ứng dụng Web Viewer (Client-side)
│   ├── app.js                  # Logic ứng dụng: tìm kiếm, bộ lọc màu, lật thẻ 3D, chế độ học tập
│   ├── index.html              # Giao diện HTML chuẩn SEO, tối ưu hiển thị
│   └── styles.css              # Style CSS Premium: Glassmorphism, Dark mode, hiệu ứng lật 3D
│
├── unified_db/                 # Cơ sở dữ liệu ảnh và manifest sau khi cắt (được lưu trên Git)
│   ├── cards/                  # Chứa toàn bộ ảnh mặt trước/sau của các thẻ đã xử lý (đặt tên theo ID thẻ)
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
└── STRUCTURE.md                # Tài liệu này (cấu trúc thư mục dự án)
```

---

## Chi tiết các thư mục chính

### 1. Thư mục `core/` (Python Processing Pipeline)
Thư mục này hoạt động như một pipeline xử lý ảnh qua các bước:
1. `pdf.py` chuyển PDF -> ảnh trang.
2. `grid.py` tìm lưới 3x3 và cắt ra 9 ô.
3. `qr.py` tìm xem ô nào có QR code (định vị mặt trước).
4. `ocr.py` đọc số thẻ trên mặt trước.
5. `pairing.py` ghép mặt trước & sau của cùng một ô lại thành một đối tượng thẻ, đặt tên theo ID của thẻ.
6. `manifest.py` lưu thông tin vào file manifest.
7. `contact_sheet.py` tạo file ảnh lưới so sánh mặt trước/sau để kiểm tra chất lượng.
8. `dist_sync.py` tự động đồng bộ kết quả sang thư mục `dist/` để chạy web cục bộ ngay lập tức.

### 2. Thư mục `src/` (Web App)
Ứng dụng web tĩnh (HTML/CSS/JS) chạy hoàn toàn ở Client-side:
- **Giao diện**: Responsive, hiển thị đẹp trên điện thoại và máy tính, hiệu ứng lật thẻ 3D mượt mà.
- **Tính năng**:
  - Tìm kiếm thẻ theo số thẻ, nhãn, hoặc âm thanh.
  - Lọc thẻ theo nhóm màu chủ đạo (được quét từ script phân tích màu).
  - Chế độ chọn bộ thẻ để học bài (Study mode).
  - Tích hợp phát âm thanh tương ứng khi lật hoặc xem thẻ.

### 3. Thư mục `unified_db/` (Dữ liệu đầu ra)
Đây là kho lưu trữ dữ liệu tập trung. Khi bạn chạy xử lý thêm bất kỳ file PDF scan mới nào, kết quả sẽ tự động gộp (merge) vào đây, cập nhật những thẻ bị trùng lặp và thêm thẻ mới mà không làm mất dữ liệu cũ.
