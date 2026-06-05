# Cardlish MVP Plan

## 0. Mục tiêu MVP

Xây một web học Cardlish tập trung vào **một thẻ học duy nhất tại một thời điểm**. MVP không cần quiz phức tạp trước; mục tiêu là học sinh tiểu học có thể mở web trên điện thoại, tablet hoặc TV và thao tác rõ ràng:

- xem 1 thẻ;
- lật mặt trước / mặt sau;
- bấm nghe âm thanh phát âm;
- chuyển thẻ trước / sau;
- luôn thấy đang chọn nút nào / vùng nào.

---

## 1. Phân tích source hiện tại

### 1.1. Cấu trúc hiện tại trong ZIP

Source hiện tại là một MVP tĩnh, gồm các phần chính:

```text
cardlish_split_mvp/
  cards/
    227_r_front.png
    227_r_back.png
    ...
  data/
    cards_manifest.json
    cards_manifest.csv
  raw_cells/
  rendered_pages/
  review_contact_sheet.png
  viewer/
    index.html
  split_cardlish_pdf.py
  README.md
```

Ngoài ra ZIP có chứa `.venv/`, làm file ZIP rất nặng. Phần này không nên đưa vào source/repo; nên thay bằng `requirements.txt` hoặc `pyproject.toml`.

### 1.2. Những gì source đã làm tốt

- `split_cardlish_pdf.py` đã render PDF thành ảnh page.
- Script đã tách layout 3x3 thành 9 ô.
- Script ghép 2 mặt theo cùng vị trí ô: A1 với A1, A2 với A2...
- Script detect QR; mặt có QR được coi là `front`.
- Script xuất `cards_manifest.json` để web có thể đọc dữ liệu.
- `viewer/index.html` đã có web tĩnh tối giản, render danh sách thẻ và có nút lật thẻ.

### 1.3. Hạn chế hiện tại

- Web đang là **grid nhiều thẻ**, chưa đúng mong muốn “1 thẻ học duy nhất”.
- JSON đang được nhúng thẳng trong `viewer/index.html`; về sau nên load từ `data/cards_manifest.json`.
- Chưa có audio local.
- QR mới được lưu dưới dạng link, chưa crawl/download file âm thanh.
- Ảnh thẻ là crop chữ nhật, một số ảnh còn nền scan/viền ngoài; bo góc mới chỉ nên làm ở mức UI, chưa có ảnh clean thật.
- Chưa có hệ thống focus/active state rõ ràng cho chuột, touch, keyboard, TV remote.
- Chưa có state học tập: thẻ hiện tại, đã học, cần ôn lại, tiến độ.

---

## 2. Kiến trúc MVP đề xuất

Có thể giữ MVP dạng static web trước, chưa cần backend phức tạp.

```text
cardlish-app/
  public/
    cards/
      233_w_front.png
      233_w_back.png
    cards_clean/
      233_w_front.webp
      233_w_back.webp
    audio/
      233_w.mp3
      234_y.mp3
    data/
      cards.json
      audio_manifest.json
  scripts/
    split_cardlish_pdf.py
    clean_card_images.py
    fetch_audio_from_qr.py
    build_manifest.py
  src/
    index.html
    styles.css
    app.js
```

Nếu muốn làm nhanh nhất, có thể tiếp tục dùng vanilla HTML/CSS/JS. Khi MVP ổn mới chuyển sang React/Vite hoặc Next.js.

---

## 3. Data model mới

Mở rộng `cards_manifest.json` hiện tại thành `cards.json`:

```json
{
  "pair_id": "235_z",
  "card_no": "235",
  "label": "Z-",
  "cell": "A3",
  "qr_url": "https://cardlish.com/z/",
  "front_image": "cards/235_z_front.png",
  "back_image": "cards/235_z_back.png",
  "front_image_clean": "cards_clean/235_z_front.webp",
  "back_image_clean": "cards_clean/235_z_back.webp",
  "audio": {
    "status": "downloaded",
    "page_url": "https://cardlish.com/z/",
    "remote_url": "",
    "local_path": "audio/235_z.mp3",
    "content_type": "audio/mpeg",
    "checksum": ""
  },
  "learning": {
    "day": null,
    "known": false,
    "last_seen_at": null
  }
}
```

### Lý do cần tách `audio`

Không nên để UI gọi trực tiếp QR URL mỗi lần học. Nên tải audio về local một lần, sau đó web phát file local để:

- nhanh hơn;
- dùng được offline/local;
- tránh phụ thuộc CORS;
- tránh hotlink liên tục sang Cardlish;
- dễ kiểm tra file nào tải thành công/thất bại.

---

## 4. Plan tính năng 1: Giao diện hiện đại, phù hợp học sinh tiểu học

### 4.1. Chuyển từ grid sang single-card learning screen

Màn hình chính chỉ có 1 thẻ lớn ở giữa:

```text
┌──────────────────────────────────────────┐
│ Cardlish                                  │
│ Thẻ 235 / 306                     12%    │
├──────────────────────────────────────────┤
│                                          │
│              [  ẢNH THẺ LỚN  ]           │
│                                          │
├──────────────────────────────────────────┤
│  ◀ Thẻ trước   🔊 Nghe âm   🔄 Lật thẻ   ▶ │
│                                          │
│  Mặt trước: Z-                            │
└──────────────────────────────────────────┘
```

### 4.2. Style giáo dục cho học sinh tiểu học

Định hướng UI:

- nền sáng, màu pastel, độ tương phản cao;
- nút lớn, bo tròn, có icon + text;
- typography lớn, dễ đọc;
- ít chữ phụ;
- thẻ lớn chiếm 60-75% màn hình;
- có mascot nhỏ hoặc emoji nhẹ, nhưng không làm rối;
- animation ngắn: flip, bounce nhẹ khi chọn đúng/nút được focus;
- mọi thao tác chính không cần menu ẩn.

### 4.3. Các nút chính trong MVP

Bắt buộc:

- `Nghe âm`
- `Lật thẻ`
- `Thẻ trước`
- `Thẻ sau`

Nên có:

- `Mặt trước / Mặt sau`
- `Đã thuộc`
- `Cần ôn lại`
- `Danh sách thẻ` dạng panel nhỏ, không phải màn hình chính.

### 4.4. State UI tối thiểu

```js
const state = {
  currentIndex: 0,
  showingFront: true,
  activeControl: "play-audio",
  audioPlaying: false
};
```

---

## 5. Plan tính năng 2: Tải audio từ QR link

### 5.1. Flow tổng quát

```text
cards_manifest.json
  ↓
Lấy qr_url của từng thẻ
  ↓
Request HTML từ qr_url
  ↓
Tìm audio URL trong HTML
  ↓
Download audio về public/audio/
  ↓
Ghi lại audio.local_path vào cards.json
  ↓
Web hiển thị nút 🔊 cạnh thẻ
```

### 5.2. Script đề xuất

Tạo script:

```text
scripts/fetch_audio_from_qr.py
```

Input:

```bash
python scripts/fetch_audio_from_qr.py \
  --manifest public/data/cards.json \
  --out public/audio \
  --delay 1.0
```

Output:

```text
public/audio/235_z.mp3
public/audio/233_w.mp3
public/data/audio_manifest.json
```

### 5.3. Cách tìm audio URL trong page QR

Script nên thử theo thứ tự:

1. Parse thẻ `<audio src="...">`.
2. Parse thẻ `<source src="...mp3">` trong `<audio>`.
3. Tìm link kết thúc bằng `.mp3`, `.m4a`, `.wav`, `.ogg`.
4. Tìm media URL trong inline script hoặc JSON embedded.
5. Nếu HTML render động, dùng Playwright headless để mở trang và bắt network request audio.

Pseudo-flow:

```python
for card in cards:
    html = fetch(card["qr_url"])
    audio_url = find_audio_url(html)

    if not audio_url:
        audio_url = find_audio_by_playwright(card["qr_url"])

    if audio_url:
        local_path = download(audio_url, f"public/audio/{card['pair_id']}.mp3")
        card["audio"] = {
            "status": "downloaded",
            "page_url": card["qr_url"],
            "remote_url": audio_url,
            "local_path": local_path
        }
    else:
        card["audio"] = {
            "status": "missing",
            "page_url": card["qr_url"],
            "error": "No audio URL found"
        }
```

### 5.4. Tích hợp nút audio trong web

Trong UI, mỗi thẻ có một nút lớn:

```html
<button id="playAudioButton" class="primary-action">
  🔊 Nghe âm
</button>
```

Logic:

```js
const audio = new Audio("../" + card.audio.local_path);
await audio.play();
```

Cần xử lý các trạng thái:

- có audio: nút active;
- đang phát: hiện animation hoặc text “Đang nghe...”;
- chưa tải được audio: nút disabled + text “Chưa có âm thanh”.

### 5.5. Lưu ý bản quyền và kỹ thuật

- Chỉ dùng cho app cá nhân/nội bộ nếu chưa có license public.
- Không hotlink audio trực tiếp trong web public.
- Tải có delay/rate-limit để không spam server.
- Lưu `remote_url`, `checksum`, `downloaded_at` để biết file nào đã tải.
- Nếu Cardlish chặn tải/cần JS dynamic, chỉ ghi trạng thái `needs_manual_review`.

---

## 6. Plan tính năng 3: Bo cạnh hình thẻ đẹp hơn

Có 2 cấp độ.

### 6.1. Cấp MVP: bo cạnh bằng CSS

Nhanh nhất, sửa ngay trong web:

```css
.card-image-shell {
  border-radius: 28px;
  overflow: hidden;
  background: white;
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.18);
}

.card-image-shell img {
  display: block;
  width: 100%;
  height: auto;
  border-radius: 28px;
}
```

Ưu điểm:

- làm nhanh;
- không phá ảnh gốc;
- đủ đẹp cho demo.

Nhược điểm:

- nếu ảnh crop còn nền scan ở góc, CSS chỉ bo cả khung ảnh chứ chưa tách đúng cạnh thẻ thật.

### 6.2. Cấp đẹp hơn: xử lý ảnh thành PNG/WebP có alpha rounded corner

Tạo script:

```text
scripts/clean_card_images.py
```

Flow:

```text
cards/*.png
  ↓
Detect vùng thẻ thật trong crop
  ↓
Perspective straighten nếu bị nghiêng nhẹ
  ↓
Crop sát thẻ
  ↓
Tạo alpha mask bo góc
  ↓
Xuất cards_clean/*.webp hoặc *.png
```

### 6.3. Thuật toán đề xuất

1. Đọc ảnh bằng OpenCV.
2. Tạo mask nền bằng threshold màu sáng / ít saturation.
3. Tìm contour lớn nhất có hình chữ nhật đứng.
4. Lấy bounding box hoặc 4 điểm góc.
5. Crop sát thẻ, thêm padding 6-12px.
6. Tạo mask bo góc bằng Pillow:

```python
mask = Image.new("L", image.size, 0)
draw = ImageDraw.Draw(mask)
draw.rounded_rectangle(
    [0, 0, image.width, image.height],
    radius=36,
    fill=255
)
image.putalpha(mask)
```

7. Save:

```text
public/cards_clean/235_z_front.webp
public/cards_clean/235_z_back.webp
```

8. Update manifest:

```json
"front_image_clean": "cards_clean/235_z_front.webp"
```

### 6.4. QA ảnh sau xử lý

Tạo contact sheet mới:

```text
review_contact_sheet_clean.png
```

Mỗi hàng gồm:

```text
original front | clean front | original back | clean back
```

Acceptance:

- không mất chữ/QR;
- không cắt mất viền thẻ;
- 4 góc trong suốt hoặc bo đều;
- ảnh hiển thị đẹp trên nền màu.

---

## 7. Plan tính năng 4: Hiển thị rõ chuột/focus đang ở đâu

Mục tiêu là dùng tốt trên:

- điện thoại cảm ứng;
- tablet;
- laptop có chuột;
- TV hoặc Android TV remote.

### 7.1. Không chỉ dùng hover

Trên TV và mobile thường không có hover thật. Cần có `active state` riêng:

```js
const controls = [
  "prev-card",
  "play-audio",
  "flip-card",
  "next-card",
  "mark-known",
  "mark-review"
];

let activeControlIndex = 1;
```

### 7.2. Focus ring lớn, dễ thấy

```css
.focusable {
  min-height: 64px;
  border-radius: 22px;
}

.focusable:focus-visible,
.focusable[data-active="true"] {
  outline: 6px solid #22c55e;
  outline-offset: 6px;
  transform: scale(1.04);
  box-shadow: 0 0 0 10px rgba(34, 197, 94, 0.18);
}
```

### 7.3. Điều khiển bằng keyboard/remote

Mapping:

```text
ArrowLeft  → thẻ trước hoặc focus nút bên trái
ArrowRight → thẻ sau hoặc focus nút bên phải
ArrowUp    → focus lên vùng thẻ
ArrowDown  → focus xuống hàng nút
Enter      → kích hoạt nút đang chọn
Space      → nghe âm hoặc lật thẻ
Escape     → quay về trạng thái mặc định
```

### 7.4. Hiển thị “đang chọn gì”

Thêm status bar:

```text
Đang chọn: 🔊 Nghe âm
```

Khi active chuyển sang nút khác:

```js
statusBar.textContent = `Đang chọn: ${activeLabel}`;
```

### 7.5. Pointer trail/cursor indicator cho màn hình lớn

Trên laptop/TV browser có chuột, thêm vòng tròn nhỏ theo pointer:

```css
.pointer-indicator {
  position: fixed;
  width: 34px;
  height: 34px;
  border-radius: 999px;
  border: 4px solid rgba(34, 197, 94, 0.9);
  pointer-events: none;
  z-index: 9999;
  transform: translate(-50%, -50%);
}
```

JS:

```js
window.addEventListener("pointermove", (event) => {
  pointerIndicator.style.left = `${event.clientX}px`;
  pointerIndicator.style.top = `${event.clientY}px`;
});
```

Trên mobile có thể ẩn indicator này và chỉ dùng active/focus ring.

---

## 8. Milestone triển khai

### Milestone 1 — Refactor MVP viewer thành single-card mode

Thời gian: 0.5-1 ngày

Việc cần làm:

- Tách CSS/JS khỏi `viewer/index.html`.
- Load data từ `data/cards_manifest.json` thay vì nhúng inline.
- Chỉ render 1 thẻ hiện tại.
- Thêm nút: nghe âm, lật, trước, sau.
- Thêm progress: `Thẻ 1 / 9`.
- Lưu `currentIndex` vào `localStorage`.

Kết quả:

- Học sinh mở web là vào thẳng 1 thẻ lớn.

### Milestone 2 — Audio downloader từ QR

Thời gian: 1 ngày cho bản đầu tiên

Việc cần làm:

- Tạo `scripts/fetch_audio_from_qr.py`.
- Đọc `cards_manifest.json`.
- Fetch QR page.
- Parse audio URL.
- Download audio vào `public/audio`.
- Ghi `audio.local_path` vào `cards.json`.
- UI phát audio local.

Kết quả:

- Mỗi thẻ có nút `🔊 Nghe âm` phát file local nếu tải thành công.

### Milestone 3 — Làm đẹp ảnh thẻ và bo góc

Thời gian: 0.5 ngày cho CSS, 1 ngày cho preprocessing ảnh

Việc cần làm:

- Thêm CSS bo góc và shadow ngay.
- Sau đó tạo `clean_card_images.py`.
- Xuất `cards_clean`.
- Update manifest dùng ảnh clean nếu có.
- Tạo `review_contact_sheet_clean.png`.

Kết quả:

- Thẻ nhìn như flashcard hiện đại, không còn cảm giác crop thô từ scanner.

### Milestone 4 — Focus/cursor cho mobile + TV

Thời gian: 0.5-1 ngày

Việc cần làm:

- Tạo danh sách `.focusable`.
- Thêm active state bằng JS.
- Hỗ trợ Arrow keys + Enter.
- Thêm focus ring lớn.
- Thêm status “Đang chọn”.
- Thêm pointer indicator cho màn hình lớn.
- Test responsive mobile portrait, tablet landscape, TV 16:9.

Kết quả:

- Dùng bằng chuột, cảm ứng, keyboard hoặc remote đều rõ đang chọn gì.

### Milestone 5 — Chuẩn bị scale lên 300 thẻ

Thời gian: sau MVP

Việc cần làm:

- Chạy splitter cho toàn bộ PDF.
- Tự động tạo manifest cho tất cả thẻ.
- Chạy audio downloader theo batch.
- Chạy image cleaner theo batch.
- Review các thẻ `needs_review = true`.
- Thêm search/lọc theo số thẻ, âm, ngày học.

---

## 9. Acceptance criteria cho MVP

MVP đạt khi:

- Web mở được bằng static server: `python -m http.server 8000`.
- Màn hình chính chỉ hiển thị 1 thẻ lớn.
- Có thể lật mặt trước/mặt sau.
- Có thể chuyển thẻ trước/sau.
- Có nút audio cạnh thẻ; nếu chưa có audio phải có trạng thái rõ ràng.
- Ảnh thẻ có bo góc đẹp và shadow.
- Nút đang được chọn có focus ring rõ trên màn hình lớn.
- Dùng được bằng chuột, touch, keyboard arrow, Enter.
- Không cần mở QR page thủ công khi học.
- Data/audio/image path nằm trong manifest, không hard-code trong UI.

---

## 10. Thứ tự ưu tiên nên làm ngay

1. Bỏ `.venv` khỏi source ZIP/repo, tạo `requirements.txt`.
2. Refactor `viewer/index.html` thành single-card mode.
3. Thêm CSS hiện đại + bo góc UI.
4. Tạo audio downloader từ QR cho 9 thẻ mẫu.
5. Tích hợp nút phát audio local.
6. Thêm focus/active state cho keyboard/TV/mobile.
7. Sau khi 9 thẻ mẫu ổn, mới chạy toàn bộ 300+ thẻ.

---

## 11. Gợi ý version MVP đầu tiên

Tên version:

```text
Cardlish Learn MVP v0.1
```

Scope v0.1:

- 9 thẻ mẫu;
- single-card viewer;
- flip front/back;
- audio nếu fetch được;
- rounded UI;
- keyboard/remote focus;
- no quiz yet.

Scope v0.2:

- import toàn bộ 306 thẻ;
- audio cache đầy đủ;
- search thẻ;
- học theo ngày;
- đánh dấu đã học/cần ôn.

Scope v0.3:

- quiz nghe âm chọn thẻ;
- spaced repetition;
- dashboard tiến độ cho phụ huynh.
