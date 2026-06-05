# Cardlish Learn — Repo Review & Cloudflare Plan

> Mục tiêu của tài liệu này: review source hiện tại trên GitHub `kinggiaan/cardlish-learn`, chuẩn chỉnh lại structure repo, chỉ ra các điểm cần sửa cho trải nghiệm học của học sinh tiểu học, và lên plan deploy lên Cloudflare.

## 0. Kết luận nhanh

Repo hiện tại đã đi đúng hướng: có pipeline tách PDF 3x3, OCR/QR, ghép 2 mặt, manifest, web viewer dạng static vanilla JS, audio local và build script cho Cloudflare. Tuy nhiên repo đang lẫn nhiều lớp khác nhau trong cùng một chỗ: source code, raw scan, generated database, public deploy assets, scripts thử nghiệm, docs, và build output. Điều này dễ gây lỗi path, dữ liệu trùng, manifest drift và deploy sai trên Cloudflare.

Plan nên đi theo hướng:

1. **Giữ MVP là static web trước**, chưa cần backend.
2. **Chuẩn hóa repo thành 4 lớp rõ ràng:** app source, processing pipeline, managed public assets, generated/local output.
3. **Chỉ cho web đọc một manifest duy nhất:** `public/data/cards.json` hoặc `dist/data/cards.json` sau build.
4. **Build ra `dist/` rồi deploy Cloudflare Pages**.
5. **Không deploy raw scan, raw cells, rendered pages, contact sheets**.
6. **Tối ưu trải nghiệm single-card learning**: 1 thẻ lớn, nút âm thanh rõ, focus rõ cho TV/mobile, gallery là màn hình phụ.

---

## 1. Review source hiện tại

### 1.1. Structure đang thấy trong repo

```text
cardlish-learn/
  core/
    contact_sheet.py
    dist_sync.py
    grid.py
    html_viewer.py
    manifest.py
    ocr.py
    pairing.py
    pdf.py
    qr.py

  public/
    audio/
      001_card.mp3
      ...
      235_z.mp3
    data/
      cards.json

  scripts/
    _check_audio.py
    _decode_qr_direct.py
    _find_audio_in_html.py
    _list_qr.py
    _page_*.html
    _probe_qr*.py
    _test_audio_download.py
    analyze_card_colors.py
    build_deploy.py
    build_manifest.py
    download_audio.py
    fetch_audio_from_qr.py

  src/
    index.html
    app.js
    styles.css

  unified_db/
    cards/
    data/
    raw_cells/
    rendered_pages/
    viewer/

  .gitignore
  README.md
  README_DEV.md
  cardlish_mvp_plan.md
  lessons_learned.md
  requirements.txt
  scan0001.pdf
  split_cardlish_pdf.py
```

### 1.2. Những điểm đã tốt

- Pipeline đã được tách thành nhiều module trong `core/`, không còn dồn hết vào một file.
- Có flow rõ: render PDF → crop grid 3x3 → detect QR → OCR → pair front/back → write manifest → contact sheet → sync ra web app.
- Viewer hiện tại đã đi về đúng MVP: single-card learning, flip 3D, gallery, search, audio, keyboard, swipe, pointer indicator.
- Có `scripts/build_deploy.py` để assemble app thành `dist/`, copy cards/audio/data, rewrite path, tạo `_headers` và `_redirects` cho Cloudflare.
- Có `lessons_learned.md`, rất tốt cho dự án kiểu pipeline vì lỗi thực tế như binary MP3, path drift, màu scan, encoding Windows sẽ lặp lại nếu không ghi lại.

### 1.3. Vấn đề chính cần sửa

#### Vấn đề 1 — Repo lẫn source và generated output

`unified_db/raw_cells`, `unified_db/rendered_pages`, `review_contact_sheet`, PDF scan, ảnh crop thô là output/debug artifact, không nên nằm chung trong source chính. Những file này làm repo phình to, deploy chậm, dễ vô tình public nội dung raw.

#### Vấn đề 2 — Có nhiều nơi chứa dữ liệu giống nhau

Hiện có ít nhất hai lớp manifest:

```text
unified_db/data/cards_manifest.json   # raw/pipeline manifest
public/data/cards.json                # web-ready manifest
```

Điều này hợp lý về mặt pipeline, nhưng cần quy ước rõ: **web app chỉ đọc web-ready manifest**. Nếu app hoặc build script có lúc đọc nhầm manifest gốc, audio/color/learning data sẽ mất.

#### Vấn đề 3 — Path dev/prod đang phải rewrite

Trong `src/app.js`, config local dùng path kiểu:

```js
DATA_URL: '../public/data/cards.json'
CARDS_BASE_PATH: '../unified_db/'
AUDIO_BASE_PATH: '../public/'
```

Khi deploy, `build_deploy.py` rewrite sang:

```js
DATA_URL: 'data/cards.json'
CARDS_BASE_PATH: ''
AUDIO_BASE_PATH: ''
```

Cách này chạy được, nhưng dễ drift. Về lâu dài nên **dev cũng chạy từ `dist/`** hoặc dùng một file `config.json` được generate theo environment.

#### Vấn đề 4 — Scripts thử nghiệm đang nằm chung với scripts production

Các file `_probe_*`, `_page_*`, `_test_*`, `_check_*` nên chuyển vào:

```text
experiments/
```

hoặc xóa khỏi main nếu không còn dùng. Thư mục `scripts/` nên chỉ chứa script có vai trò rõ ràng trong pipeline/build.

#### Vấn đề 5 — Audio downloader bị trùng chức năng

Hiện có cả:

```text
scripts/download_audio.py
scripts/fetch_audio_from_qr.py
```

Trong `lessons_learned.md`, bạn đã phát hiện QR URL có thể chính là MP3 binary trực tiếp, không phải HTML. Vì vậy nên hợp nhất thành một script duy nhất, ví dụ:

```text
scripts/assets/sync_audio.py
```

Flow đúng là:

```text
request QR URL
  ↓
check Content-Type / magic bytes
  ↓
if audio/* hoặc ID3/FFFB → save binary
  ↓
else if text/html → parse HTML tìm audio URL
  ↓
else mark missing/error
```

#### Vấn đề 6 — UX keyboard/TV cần nhất quán hơn

Code hiện tại đã có `activeControlIndex`, `CONTROLS`, status “Đang chọn”, pointer indicator. Đây là nền tốt. Nhưng mapping hiện tại nên được tinh chỉnh để tránh bất ngờ cho TV remote:

- Không nên để `ArrowUp` tự động flip thẻ ngay; nên dùng `ArrowUp` để chuyển focus lên vùng thẻ, `Enter` mới flip.
- Không nên để `ArrowLeft` vừa di chuyển focus vừa tự chuyển thẻ ở mép; trên TV người dùng cần hành vi nhất quán.
- Nên có một “roving focus” rõ ràng: D-pad chỉ di chuyển focus, Enter mới kích hoạt.

---

## 2. Structure repo đề xuất

### 2.1. Structure ngắn hạn — giữ vanilla JS, ít thay đổi nhất

```text
cardlish-learn/
  README.md
  requirements.txt
  .gitignore

  docs/
    architecture.md
    deployment-cloudflare.md
    pipeline.md
    ux-spec.md
    lessons-learned.md
    repo-review-plan.md

  src/
    index.html
    app/
      config.js
      state.js
      cards.js
      audio.js
      gallery.js
      input.js
      storage.js
      app.js
    styles/
      tokens.css
      base.css
      layout.css
      components.css
      gallery.css
      responsive.css

  scripts/
    pipeline/
      split_pdf.py
      render_pdf.py
      crop_grid.py
      detect_qr.py
      extract_ocr.py
      pair_cards.py
      write_manifest.py
      make_contact_sheet.py
    assets/
      build_manifest.py
      sync_audio.py
      clean_card_images.py
      analyze_card_colors.py
      validate_assets.py
    build/
      build_static.py

  public/
    data/
      cards.json
    cards/
      233_w_front.webp
      233_w_back.webp
    audio/
      233_w.mp3

  samples/
    scan0001.pdf

  input/              # gitignored
    scan0002.pdf
    scan0003.pdf

  work/               # gitignored
    unified_db/
    raw_cells/
    rendered_pages/
    review/

  dist/               # gitignored, Cloudflare build output
```

### 2.2. Structure dài hạn — nếu chuyển sang Vite/React

Chỉ nên làm sau khi MVP static chạy ổn.

```text
cardlish-learn/
  package.json
  vite.config.ts
  wrangler.toml hoặc wrangler.jsonc

  src/
    main.tsx
    App.tsx
    components/
      CardStage.tsx
      ActionBar.tsx
      GalleryDrawer.tsx
      AudioButton.tsx
      FocusRing.tsx
    lib/
      cards.ts
      audio.ts
      storage.ts
      navigation.ts
    styles/
      tokens.css
      app.css

  public/
    data/cards.json
    cards/*.webp
    audio/*.mp3

  scripts/
    ...pipeline giữ bằng Python...

  dist/
```

### 2.3. Quy tắc đặt tên thư mục

- `src/`: chỉ chứa source của web app.
- `scripts/`: chỉ chứa script có thể chạy lại.
- `public/`: chỉ chứa asset mà web cần dùng ở runtime.
- `work/`: output trung gian, không commit.
- `dist/`: output deploy, không sửa tay.
- `docs/`: tài liệu project.
- `samples/`: file mẫu nhỏ để test pipeline, không chứa toàn bộ raw scan.

---

## 3. `.gitignore` đề xuất

```gitignore
# Python
.venv/
__pycache__/
*.py[cod]
*.pyo
.pytest_cache/

# Build output
dist/

# Local input/output
input/
work/
output/
cardlish_output/
unified_db/raw_cells/
unified_db/rendered_pages/
unified_db/review_contact_sheet_*.png
review_contact_sheet*.png

# Raw scans
scan*.pdf
*.tif
*.tiff

# Keep sample only if needed
!samples/scan0001.pdf

# OS / editor
.DS_Store
Thumbs.db
desktop.ini
.vscode/
.idea/
*.swp
*.swo

# Logs
*.log
```

Gợi ý: nếu vẫn muốn giữ `unified_db/cards` và `public/audio` trong repo cho deploy nhanh, hãy giữ riêng phần **optimized runtime assets**, không commit raw/debug assets.

---

## 4. Single Source of Truth cho dữ liệu

### 4.1. Quy ước manifest

Nên có 2 manifest nhưng vai trò thật rõ:

```text
work/unified_db/data/cards_manifest.json
  → output thô từ scanner/pipeline
  → không cho web đọc trực tiếp

public/data/cards.json
  → web-ready manifest
  → có audio/color/learning/default metadata
  → web app chỉ đọc file này
```

### 4.2. Data contract cho `public/data/cards.json`

```json
{
  "pair_id": "235_z",
  "card_no": "235",
  "label": "Z-",
  "cell": "A3",
  "qr_url": "https://cardlish.com/z/",
  "front_image": "cards/235_z_front.webp",
  "back_image": "cards/235_z_back.webp",
  "audio": {
    "status": "downloaded",
    "page_url": "https://cardlish.com/z/",
    "remote_url": "https://cardlish.com/z/",
    "local_path": "audio/235_z.mp3",
    "content_type": "audio/mpeg",
    "checksum": ""
  },
  "color": {
    "group": "gray",
    "hex": "#6b7280"
  },
  "learning": {
    "day": null,
    "known": false,
    "last_seen_at": null,
    "review_count": 0
  },
  "needs_review": false,
  "review_note": ""
}
```

### 4.3. Validation bắt buộc trước deploy

Tạo script:

```text
scripts/assets/validate_assets.py
```

Check:

- mỗi card có `pair_id` unique;
- `front_image` tồn tại;
- `back_image` tồn tại hoặc có fallback;
- nếu `audio.status = downloaded` thì `audio.local_path` tồn tại;
- không có card `needs_review = true` trong build production, hoặc vẫn cho phép nhưng hiện badge review;
- không có path bắt đầu bằng `../` trong manifest production;
- tổng số thẻ đúng kỳ vọng.

Command:

```bash
python scripts/assets/validate_assets.py --manifest public/data/cards.json --root public
```

---

## 5. Plan refactor source web

### 5.1. Hiện tại

`src/app.js` đang chứa quá nhiều phần trong một file:

- config;
- state;
- data loader;
- renderer;
- audio;
- gallery;
- keyboard;
- swipe;
- pointer;
- localStorage;
- error handling.

Với MVP thì được, nhưng khi thêm quiz/spaced repetition sẽ khó maintain.

### 5.2. Tách module đề xuất

```text
src/app/
  config.js       # CONFIG, runtime path
  state.js        # state + galleryState
  cards.js        # loadCards, sort, filter, preload
  render.js       # renderCard, updateSideText, updateProgress
  audio.js        # playAudio, stopAudio, updateAudioButton
  gallery.js      # open/close/filter gallery
  input.js        # keyboard, touch, pointer, focus manager
  storage.js      # localStorage wrapper
  utils.js        # escapeHtml, clamp, etc.
  main.js         # init
```

Trong `index.html` dùng module:

```html
<script type="module" src="app/main.js"></script>
```

### 5.3. Cách giảm path drift

Thay vì rewrite hard-code trong `app.js`, tạo `public/config.json` hoặc `dist/config.json`:

```json
{
  "dataUrl": "data/cards.json",
  "cardsBasePath": "",
  "audioBasePath": ""
}
```

Web app load config trước:

```js
const config = await fetch('config.json').then(r => r.json());
```

Nếu muốn đơn giản hơn: **luôn dev bằng `dist/`**:

```bash
python scripts/build/build_static.py --output dist
python -m http.server 8000 -d dist
```

Khi đó dev và prod dùng cùng path, không cần rewrite nhiều.

---

## 6. Gợi ý sửa UX cho học sinh tiểu học

### 6.1. Nguyên tắc màn hình chính

Màn hình chính nên chỉ có một nhiệm vụ: học một thẻ.

```text
┌────────────────────────────────────────────┐
│ Cardlish Learn       Thẻ 235 / 306   77%   │
├────────────────────────────────────────────┤
│                                            │
│              [ ẢNH THẺ RẤT LỚN ]           │
│                                            │
│              Chạm để lật thẻ               │
│                                            │
├────────────────────────────────────────────┤
│  ◀ Trước   🔊 Nghe âm   🔄 Lật   Sau ▶     │
│                                            │
│  Đang chọn: 🔊 Nghe âm                     │
└────────────────────────────────────────────┘
```

### 6.2. Kích thước điều khiển

- Button chính tối thiểu `64px` cao trên desktop/tablet.
- Trên TV nên `72px` hoặc hơn.
- Icon + text luôn đi cùng nhau, không chỉ icon.
- Focus ring dày, tương phản cao.
- Không đặt nút quan trọng sát mép màn hình mobile.

### 6.3. Audio UX

Trạng thái nút audio:

```text
Có audio       → 🔊 Nghe âm
Đang phát      → 🔊 Đang nghe...
Không có audio → 🔇 Chưa có âm
Lỗi file       → ⚠️ Lỗi âm thanh
```

Hành vi:

- Bấm lại khi đang phát → replay hoặc stop/replay; nên chọn replay vì trẻ nhỏ thường muốn nghe lại.
- Khi chuyển thẻ → dừng audio cũ.
- Preload audio của thẻ hiện tại và thẻ kế tiếp nếu có.
- Không gọi QR/Cardlish trực tiếp từ browser runtime; chỉ phát local `audio/*.mp3`.

### 6.4. Điều hướng TV/mobile

Nên dùng “roving focus”:

```text
ArrowLeft  → focus nút bên trái
ArrowRight → focus nút bên phải
ArrowUp    → focus vùng thẻ
ArrowDown  → focus hàng nút
Enter      → kích hoạt vùng/nút đang focus
Space      → kích hoạt vùng/nút đang focus
Back/Escape → đóng gallery hoặc reset focus về Nghe âm
```

Không nên tự chuyển thẻ khi bấm ArrowLeft/Right nếu focus chưa nằm trên nút Trước/Sau. Với TV remote, người dùng cần thấy focus đang ở đâu rồi mới bấm Enter.

### 6.5. Vùng thẻ cũng nên focus được

Hiện thẻ click để flip. Nên thêm:

```html
<button class="card-stage focusable" data-action="flip-card" aria-label="Lật thẻ">
  ...
</button>
```

Hoặc giữ div nhưng thêm:

```html
<div tabindex="0" role="button" aria-label="Lật thẻ">
```

### 6.6. Gallery nên là màn hình phụ

Gallery hiện đã có search/filter/count. Nhưng với học sinh tiểu học, màn hình chính không nên quá nhiều lựa chọn. Đề xuất:

- Nút gallery chỉ là “Chọn thẻ”.
- Gallery dạng drawer hoặc full-screen overlay.
- Có preset lớn: `Học 10 thẻ`, `Học 20 thẻ`, `Tất cả`.
- Search dành cho phụ huynh/giáo viên, không đặt quá nổi.
- Card grid dùng thumbnail WebP nhẹ, không dùng ảnh full-res.

### 6.7. Progress học

Thêm local progress đơn giản:

```json
{
  "currentIndex": 12,
  "known": ["235_z", "234_y"],
  "review": ["233_w"],
  "lastSessionAt": "2026-06-05T..."
}
```

UI:

```text
✅ Đã thuộc
🔁 Cần ôn
```

Đây là bước trước khi làm spaced repetition thật.

### 6.8. Accessibility

- `alt` ảnh nên chứa số thẻ + label + mặt trước/sau.
- Nút disabled vẫn cần text rõ: “Chưa có âm”.
- Tôn trọng `prefers-reduced-motion` để giảm animation flip/bounce.
- Dùng `aria-live="polite"` cho status “Đang chọn”.
- Không dùng màu làm tín hiệu duy nhất; cần text hoặc icon đi kèm.

---

## 7. Flow bo cạnh và làm đẹp ảnh thẻ

### 7.1. Cấp MVP — CSS-only

Trong `styles/components.css`:

```css
.card-image-shell {
  border-radius: 28px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.18);
}

.card-image-shell img {
  display: block;
  width: 100%;
  height: auto;
  border-radius: 28px;
  object-fit: contain;
}
```

### 7.2. Cấp production — clean image pipeline

Tạo:

```text
scripts/assets/clean_card_images.py
```

Flow:

```text
work/unified_db/cards/*.png
  ↓
OpenCV detect card contour
  ↓
perspective transform nếu nghiêng
  ↓
crop sát viền thẻ
  ↓
Pillow rounded alpha mask
  ↓
resize/compress WebP
  ↓
public/cards/*.webp
```

Output:

```text
public/cards/235_z_front.webp
public/cards/235_z_back.webp
```

Manifest sau clean:

```json
"front_image": "cards/235_z_front.webp",
"back_image": "cards/235_z_back.webp"
```

### 7.3. QA sau clean

Tạo contact sheet:

```text
work/review/review_contact_sheet_clean.png
```

Mỗi hàng:

```text
original front | clean front | original back | clean back
```

Acceptance:

- không mất QR;
- không cắt mất chữ;
- không cắt mất số thẻ;
- 4 góc bo đều;
- ảnh không bị méo;
- ảnh đẹp trên nền pastel.

---

## 8. Flow audio từ QR

### 8.1. Hợp nhất script

Thay 2 script hiện tại bằng một script chính:

```text
scripts/assets/sync_audio.py
```

Giữ `_probe_*` vào `experiments/` nếu còn cần debug.

### 8.2. Flow đúng

```text
public/data/cards.json
  ↓
for each card.qr_url
  ↓
request stream
  ↓
check status/content-type/magic bytes
  ↓
if MP3 → save audio/{pair_id}.mp3
  ↓
if HTML → parse audio URL → download
  ↓
update card.audio
  ↓
write public/data/cards.json
```

### 8.3. Trạng thái audio

```json
"audio": {
  "status": "downloaded | missing | error | pending",
  "page_url": "https://cardlish.com/z/",
  "remote_url": "https://cardlish.com/z/",
  "local_path": "audio/235_z.mp3",
  "content_type": "audio/mpeg",
  "checksum": "...",
  "downloaded_at": "2026-06-05T...",
  "error": ""
}
```

### 8.4. Command

```bash
python scripts/assets/sync_audio.py \
  --manifest public/data/cards.json \
  --out public/audio \
  --delay 1.0
```

### 8.5. Lưu ý

- Có delay để tránh spam server.
- Không hotlink audio trực tiếp từ app production.
- Nếu deploy public, cần cân nhắc bản quyền/giấy phép với Cardlish.
- Nếu muốn chỉ dùng cá nhân/gia đình, có thể dùng Cloudflare Access để giới hạn người truy cập.

---

## 9. Cloudflare deployment plan

### 9.1. Khuyến nghị cho MVP hiện tại

Dùng **Cloudflare Pages static site**.

Cấu hình đề xuất:

```text
Framework preset: None
Production branch: main
Root directory: /
Build command: python scripts/build_deploy.py --output dist
Build output directory: dist
```

Lý do: app hiện tại là static HTML/CSS/JS, không cần backend. Script `build_deploy.py` chỉ dùng Python standard library cho copy/rewrite/header, nên có thể chạy nhẹ. Nếu Cloudflare build image không chạy Python như kỳ vọng, phương án dự phòng là chạy build ở GitHub Actions rồi deploy bằng Wrangler.

### 9.2. Build command local trước khi push

```bash
python scripts/build_deploy.py --output dist
python -m http.server 8000 -d dist
```

Test:

```text
http://localhost:8000
```

Checklist trước deploy:

- `dist/index.html` mở được.
- `dist/data/cards.json` load được.
- `dist/cards/*.png|webp` load được.
- `dist/audio/*.mp3` phát được.
- Không còn request tới `../unified_db` hoặc `../public`.
- DevTools Network không có 404.

### 9.3. Không commit `dist/`

`dist/` nên là build output. Cloudflare tự build từ repo. Nếu deploy gấp và không muốn build trên Cloudflare, có thể tạm commit `dist/` vào branch `deploy`, nhưng không nên dùng lâu dài.

### 9.4. `_headers`

Giữ `_headers` trong `dist/`, generate từ build script.

Đề xuất:

```text
/*.html
  Cache-Control: public, max-age=0, must-revalidate

/
  Cache-Control: public, max-age=0, must-revalidate

/*.css
  Cache-Control: public, max-age=86400, stale-while-revalidate=3600

/*.js
  Cache-Control: public, max-age=86400, stale-while-revalidate=3600

/cards/*
  Cache-Control: public, max-age=2592000, immutable

/audio/*
  Cache-Control: public, max-age=2592000, immutable

/data/*
  Cache-Control: public, max-age=3600, stale-while-revalidate=600

/*
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
```

### 9.5. `_redirects`

Nếu app chỉ có `/`, có thể không cần. Nếu sau này có SPA route như `/learn`, `/gallery`, thêm:

```text
/* /index.html 200
```

### 9.6. Asset limit

Với 306 thẻ:

```text
306 cards x 2 images = 612 image files
306 audio files ≈ 306 mp3 files
JSON/CSS/JS ≈ vài file
```

Số file này vẫn nhỏ so với limit Pages thông thường. Tuy nhiên cần tránh deploy raw scans/rendered pages vì những file này lớn và không cần cho runtime.

Nếu sau này ảnh/audio lớn hoặc muốn lưu toàn bộ raw dataset, dùng:

```text
Cloudflare Pages → app shell
Cloudflare R2    → raw/high-res/audio archive
```

### 9.7. Nếu chuyển sang Vite

Khi chuyển sang Vite/React, dùng cấu hình chuẩn hơn:

```text
Build command: npm run build
Build output directory: dist
```

`package.json` tối thiểu:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }
}
```

Nhưng hiện tại chưa cần chuyển nếu mục tiêu là MVP nhanh.

---

## 10. Milestone triển khai

### Milestone 1 — Dọn repo và chuẩn hóa build

Mục tiêu: repo sạch, deploy được bằng `dist/`.

Tasks:

- [ ] Move `README_DEV.md` → `docs/developer-guide.md`.
- [ ] Move `lessons_learned.md` → `docs/lessons-learned.md`.
- [ ] Move `cardlish_mvp_plan.md` → `docs/roadmap-mvp.md`.
- [ ] Move scripts thử nghiệm `_probe_*`, `_page_*`, `_test_*` → `experiments/` hoặc xóa.
- [ ] Không commit `unified_db/raw_cells` và `unified_db/rendered_pages`.
- [ ] Không commit raw scan PDF ngoài file sample.
- [ ] Rename `scripts/build_deploy.py` → `scripts/build/build_static.py` hoặc giữ tên cũ nhưng document rõ.
- [ ] Add `scripts/assets/validate_assets.py`.
- [ ] Chạy `python scripts/build_deploy.py --output dist` và test local.

Acceptance:

- Repo nhìn rõ source/app/pipeline/assets/docs.
- `dist/` build clean từ repo.
- Không có 404 khi serve `dist/`.

### Milestone 2 — Chuẩn hóa manifest/audio

Mục tiêu: một manifest web-ready, audio local phát ổn.

Tasks:

- [ ] Hợp nhất `download_audio.py` và `fetch_audio_from_qr.py` thành `sync_audio.py`.
- [ ] `sync_audio.py` check `Content-Type` trước khi parse HTML.
- [ ] Update `public/data/cards.json` sau khi tải audio.
- [ ] Validate audio file tồn tại trước deploy.
- [ ] UI audio có 4 trạng thái: available, playing, missing, error.

Acceptance:

- Không còn “Chưa có âm” sai do app đọc nhầm manifest.
- Audio phát từ `dist/audio/*.mp3`.
- Không hotlink QR runtime.

### Milestone 3 — UX single-card cho trẻ em

Mục tiêu: học sinh mở web là học được ngay.

Tasks:

- [ ] Màn hình chính chỉ 1 card lớn.
- [ ] Action bar sticky dưới cùng trên mobile.
- [ ] Nút lớn: Trước, Nghe âm, Lật, Sau.
- [ ] Thêm `Đã thuộc` và `Cần ôn` sau khi audio/flip ổn.
- [ ] Gallery chuyển thành màn hình phụ.
- [ ] Text status “Đang chọn” dùng `aria-live`.
- [ ] Hỗ trợ reduced motion.

Acceptance:

- Dùng được trên điện thoại bằng một tay.
- Dùng được trên TV bằng remote/D-pad.
- Focus ring luôn rõ.

### Milestone 4 — Làm đẹp ảnh

Mục tiêu: ảnh thẻ nhìn như flashcard thật, không còn cảm giác crop thô.

Tasks:

- [ ] CSS rounded shell ngay trong UI.
- [ ] Tạo `clean_card_images.py`.
- [ ] Xuất WebP vào `public/cards/`.
- [ ] Manifest dùng WebP runtime.
- [ ] Gallery dùng thumbnail nhẹ.
- [ ] QA bằng contact sheet clean.

Acceptance:

- Không mất QR/chữ/số thẻ.
- 4 góc bo đều.
- Ảnh nhẹ hơn PNG gốc.

### Milestone 5 — Cloudflare production

Mục tiêu: deploy ổn, cache đúng, dễ rollback.

Tasks:

- [ ] Cloudflare Pages connect GitHub.
- [ ] Build command: `python scripts/build_deploy.py --output dist`.
- [ ] Output directory: `dist`.
- [ ] Verify `_headers` trên production.
- [ ] Verify audio/image cache.
- [ ] Thêm custom domain nếu cần.
- [ ] Cân nhắc Cloudflare Access nếu app chỉ dùng cá nhân/nội bộ.

Acceptance:

- Deploy từ push lên `main`.
- Preview deploy hoạt động cho PR.
- Production không request raw assets.
- Không có file đơn lẻ quá lớn.

---

## 11. Thứ tự ưu tiên làm ngay

1. **Dọn repo:** tách docs/scripts/experiments/generated assets.
2. **Build từ `src + public` ra `dist` duy nhất.**
3. **Dev bằng `dist/` để hết path drift.**
4. **Hợp nhất audio downloader.**
5. **Validate manifest/assets trước deploy.**
6. **Sửa keyboard/TV navigation thành roving focus nhất quán.**
7. **Tối ưu ảnh: CSS rounded trước, WebP cleaner sau.**
8. **Deploy Cloudflare Pages static.**

---

## 12. Suggested PR breakdown

### PR 1 — Repo cleanup

```text
Move docs
Move experiments
Update .gitignore
Add docs/repo-review-plan.md
```

### PR 2 — Build reliability

```text
Refactor build_deploy.py
Add validate_assets.py
Make local dev serve dist
Document Cloudflare settings
```

### PR 3 — Audio sync

```text
Merge audio scripts
Content-Type first
Update manifest schema
Improve audio button states
```

### PR 4 — UX controls

```text
Roving focus
Card focusable
TV remote mapping
Status aria-live
Reduced motion
```

### PR 5 — Image cleaner

```text
CSS rounded card
Clean image script
WebP output
Review contact sheet clean
```

---

## 13. Commands đề xuất sau refactor

### Scan/import PDF

```bash
python scripts/pipeline/split_pdf.py input/scan0002.pdf --out work/unified_db --dpi 200
```

### Build manifest cho web

```bash
python scripts/assets/build_manifest.py \
  --input work/unified_db/data/cards_manifest.json \
  --output public/data/cards.json
```

### Tải audio

```bash
python scripts/assets/sync_audio.py \
  --manifest public/data/cards.json \
  --out public/audio \
  --delay 1.0
```

### Clean ảnh

```bash
python scripts/assets/clean_card_images.py \
  --manifest public/data/cards.json \
  --input work/unified_db/cards \
  --out public/cards
```

### Validate trước deploy

```bash
python scripts/assets/validate_assets.py \
  --manifest public/data/cards.json \
  --root public
```

### Build static

```bash
python scripts/build_deploy.py --output dist
```

### Test local như production

```bash
python -m http.server 8000 -d dist
```

---

## 14. Ghi chú bản quyền

Nếu app chỉ dùng cá nhân/gia đình/lớp học nội bộ từ bộ thẻ đã mua, cách scan/audio local có thể phù hợp cho MVP cá nhân. Nếu public web/app cho nhiều người, cần xin quyền Cardlish trước khi public hình thẻ, text, QR/audio, hoặc giới hạn truy cập bằng Cloudflare Access.
