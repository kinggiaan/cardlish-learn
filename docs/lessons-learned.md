# Cardlish Learn — Bug Log & Lessons Learned

> Tài liệu ghi lại các lỗi gặp phải, nguyên nhân gốc, cách sửa, và chiến lược phòng tránh cho các dự án sau.

---

## Bug #1: Tải file binary (MP3) nhưng xử lý như text

### Triệu chứng
- Script `fetch_audio_from_qr.py` báo **"No .mp3 URLs found in HTML"**
- Trang QR (vd: `cardlish.com/short-a/`) trả về status 200 nhưng không tìm thấy tag `<audio>` hay URL `.mp3` nào

### Nguyên nhân gốc
URL QR **chính là file MP3 trực tiếp**, không phải trang HTML. Server cardlish.com trả về `audio/mpeg` binary content. Nhưng script:
1. Dùng `r.text` (decode thành string) thay vì `r.content` (binary)
2. Rồi dùng regex tìm `<audio>`, `.mp3` trong "HTML" — tất nhiên không tìm thấy gì
3. Kết luận sai: "trang không có audio"

### Bằng chứng
Khi lưu response ra file `.html` rồi mở xem, dòng đầu tiên là:
```
ID3♥...TIT2........Short ATPE1........Craig Tran
```
→ Đây là ID3 tag của MP3, không phải HTML!

### Fix
```python
# SAI: Parse response dạng text
html = r.text
mp3s = re.findall(r'\.mp3', html)  # Tìm trong "text" của binary → fail

# ĐÚNG: Kiểm tra Content-Type trước, rồi lưu binary
r = requests.get(url, stream=True)
content_type = r.headers.get("Content-Type", "")

if "audio" in content_type:
    # Đây là file audio trực tiếp — lưu binary
    with open(output, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
else:
    # Đây mới là HTML — parse
    html = r.text
```

### Phòng tránh

> [!IMPORTANT]
> **Luôn kiểm tra `Content-Type` trước khi quyết định xử lý response.**

```python
# Pattern an toàn cho mọi URL không rõ loại
r = requests.get(url, stream=True, timeout=15)
ct = r.headers.get("Content-Type", "")

if "text/html" in ct:
    process_as_html(r.text)
elif "audio/" in ct:
    save_as_binary(r, output_path)
elif "image/" in ct:
    save_as_binary(r, output_path)
elif "application/json" in ct:
    process_as_json(r.json())
else:
    # Kiểm tra magic bytes
    first_bytes = r.content[:4]
    if first_bytes[:3] == b"ID3":          # MP3
        save_binary(...)
    elif first_bytes[:4] == b"\x89PNG":    # PNG
        save_binary(...)
    elif first_bytes[:2] == b"\xff\xd8":   # JPEG
        save_binary(...)
    else:
        process_as_text(r.text)
```

### Checklist cho lần sau
- [ ] URL trả về content gì? Kiểm tra `Content-Type` header
- [ ] Nếu binary → dùng `r.content` hoặc `r.iter_content()`, KHÔNG dùng `r.text`
- [ ] Nếu không chắc → kiểm tra magic bytes (ID3, PNG, JPEG, etc.)
- [ ] Lưu file thử 1 cái rồi mở xem trước khi batch process

---

## Bug #2: App đọc sai manifest (không có audio data)

### Triệu chứng
- Web hiện "Chưa có âm" cho tất cả thẻ
- Audio đã tải xong 53 files, manifest `public/data/cards.json` đã cập nhật `status: "downloaded"`

### Nguyên nhân gốc
`app.js` CONFIG trỏ đến **manifest gốc**:
```js
DATA_URL: '../unified_db/data/cards_manifest.json'  // ← Manifest gốc, KHÔNG có audio
```
Thay vị manifest đã build (có audio data):
```js
DATA_URL: '../public/data/cards.json'  // ← Manifest đã build, CÓ audio
```

### Tại sao xảy ra
Dự án có **2 manifest**:
1. `unified_db/data/cards_manifest.json` — nguồn gốc, raw data từ quét PDF
2. `public/data/cards.json` — bản build, đã lọc + thêm audio/color data

Khi build frontend, đã trỏ nhầm sang manifest gốc. Audio data chỉ tồn tại ở manifest build.

### Fix
```diff
- DATA_URL: '../unified_db/data/cards_manifest.json',
+ DATA_URL: '../public/data/cards.json',
- AUDIO_BASE_PATH: '../public/audio/',
+ AUDIO_BASE_PATH: '../public/',
```

### Phòng tránh

> [!IMPORTANT]
> **Một dự án chỉ nên có 1 manifest duy nhất (Single Source of Truth).**

Nếu có pipeline build:
```
source.json → build script → output.json → web app
```
Thì web app **chỉ đọc output.json**, KHÔNG BAO GIỜ đọc source.json.

### Checklist
- [ ] Web app đọc file nào? Kiểm tra CONFIG
- [ ] File đó có đầy đủ data cần thiết không? (audio, color, etc.)
- [ ] Sau khi chạy script update data → web app có tự nhận data mới không?
- [ ] Ghi rõ trong README: manifest nào dùng cho gì

---

## Bug #3: Windows console encoding crash (cp1252 vs Unicode)

### Triệu chứng
```
UnicodeEncodeError: 'charmap' codec can't encode character '\u0292' 
in position 34: character maps to <undefined>
```
Script Python crash khi `print()` ký tự Unicode (emoji, tiếng Việt, IPA symbols).

### Nguyên nhân gốc
Windows PowerShell mặc định dùng encoding `cp1252` (Western European), không hỗ trợ:
- Emoji: 🔴 🟢 🔵
- Tiếng Việt có dấu: ồ, ắ, ự
- IPA symbols: ʒ (voiced postalveolar fricative)

### Fix
Thêm ở đầu script Python:
```python
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
```

Hoặc dùng environment variable:
```powershell
$env:PYTHONIOENCODING = "utf-8"
python my_script.py
```

### Phòng tránh

> [!TIP]
> **Mọi script Python chạy trên Windows nên có UTF-8 stdout wrapper ở đầu file.**

```python
# Đặt ở đầu mọi script có print() tiếng Việt/emoji
import sys, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
```

Hoặc tránh dùng emoji/Unicode trong output:
```python
# SAI
print("✅ Hoàn tất")
print(f"Màu: Hồng")

# ĐÚNG (safe cho mọi console)
print("[OK] Hoan tat")
print(f"Color: pink")
```

---

## Bug #4: Cardlish.com chặn kết nối từ script (SSL Reset)

### Triệu chứng
```
ConnectionResetError: [WinError 10054] An existing connection was 
forcibly closed by the remote host
```
Xảy ra khi dùng `requests.get()` để fetch trang cardlish.com.

### Nguyên nhân gốc
Cardlish.com dùng **Cloudflare bot protection** hoặc TLS fingerprinting. Khi Python `requests` kết nối:
1. TLS handshake có fingerprint khác browser thật
2. Server nhận ra → reset connection
3. Đôi khi cho phép (lần sau chạy OK), đôi khi không → behavior không ổn định

### Tại sao lần sau lại OK?
Lần đầu (probe HTML): `requests` gửi `Accept: text/html` → server nghi ngờ scraping → block
Lần sau (download audio): `requests` gửi request đơn giản → server cho qua (vì URL là static file)

Cũng có thể: Cloudflare rate limit, sau khi chờ đủ lâu thì unblock.

### Fix
Trong trường hợp này, không cần fix vì URL QR serve file trực tiếp. Nhưng nếu cần scrape trang HTML thật:

```python
# Option 1: Headers giống browser hơn
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}

# Option 2: Dùng Playwright (headless browser thật)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://cardlish.com/short-a/")
    html = page.content()

# Option 3: Dùng curl-cffi (TLS fingerprint impersonation)  
from curl_cffi import requests as cffi_requests
r = cffi_requests.get(url, impersonate="chrome")
```

### Phòng tránh

> [!WARNING]
> **Trước khi build scraper phức tạp, luôn kiểm tra xem URL trả về gì.**

```python
# Bước 1: Thử tải 1 URL, kiểm tra response
r = requests.get(url, stream=True, timeout=10)
print(f"Status: {r.status_code}")
print(f"Content-Type: {r.headers.get('Content-Type')}")
print(f"Content-Length: {r.headers.get('Content-Length')}")
first_bytes = r.content[:20]
print(f"First bytes: {first_bytes}")
print(f"First bytes hex: {first_bytes.hex()}")

# Bước 2: Nếu status 403/503 → có bot protection
# Bước 3: Nếu content là binary → KHÔNG CẦN scrape HTML
```

---

## Bug #5: Path drift giữa dev và production

### Triệu chứng
Web hoạt động local nhưng deploy lên Cloudflare thì 404 hình ảnh/audio.

### Nguyên nhân gốc
Local dev structure:
```
src/index.html          ← web app ở đây
unified_db/cards/       ← ảnh ở đây (path: ../unified_db/cards/)
public/audio/           ← audio ở đây (path: ../public/audio/)
```

Production (dist/) structure:
```
dist/index.html         ← web app
dist/cards/             ← ảnh (path: cards/)
dist/audio/             ← audio (path: audio/)
```

Path tương đối **khác nhau** giữa 2 môi trường!

### Fix
Build script `build_deploy.py` tự động rewrite paths:
```python
replacements = [
    (r"DATA_URL:\s*['\"].*?['\"]",       "DATA_URL: 'data/cards.json'"),
    (r"CARDS_BASE_PATH:\s*['\"].*?['\"]", "CARDS_BASE_PATH: ''"),
    (r"AUDIO_BASE_PATH:\s*['\"].*?['\"]", "AUDIO_BASE_PATH: ''"),
]
for pattern, replacement in replacements:
    content = re.sub(pattern, replacement, content)
```

### Phòng tránh

> [!TIP]
> **Thiết kế path system từ đầu để giảm drift.**

```javascript
// Pattern tốt: dùng 1 BASE_URL, tự detect environment
const CONFIG = {
  BASE_URL: window.location.hostname === 'localhost' 
    ? '../public/' 
    : './',
};

// Hoặc: dùng <base> tag trong HTML
// <base href="../public/">   (dev)
// <base href="./">           (prod — set by build script)
```

Hoặc đơn giản nhất: **dev cũng serve từ dist/**:
```bash
python scripts/build_deploy.py
python -m http.server 8000 -d dist
```

---

## Bug #6: Nhận diện sai màu sắc thẻ phụ âm do nhiễu quét (Scanned Card Color Classification)

### Triệu chứng
- Các thẻ phụ âm (consonants/blends) màu Xám (số hiệu thẻ `200–299` và thẻ đơn lẻ `277`) bị phân loại sai thành các nhóm màu nổi bật như Xanh (blue/cyan), Cam, Vàng, Lá (green) trong file `cards.json`.
- Người dùng thấy các thẻ phụ âm này bị trộn lẫn vào các bộ thẻ học màu khác trong thư viện của ứng dụng.

### Nguyên nhân gốc
- Thiết bị quét (scanner) tự động áp một lớp ám màu nhẹ (color cast/tint) hoặc sinh ra nhiễu hạt màu (color noise) lên vùng nền xám của thẻ.
- Thuật toán phân tích màu (`scripts/analyze_card_colors.py`) cố gắng lọc bỏ các pixel trung tính có độ bão hòa thấp (`sat < 0.15`) để tìm ra màu chủ đạo. Khi nền xám bị loại bỏ hoàn toàn, thuật toán chỉ còn lại các điểm ảnh nhiễu màu này để phân tích, dẫn đến việc phân loại sai vào dải màu tương ứng của nhiễu.

### Fix
Bổ sung một quy tắc ghi đè cứng (consonant color override) cho dải số thẻ phụ âm trong [analyze_card_colors.py](file:///d:/37/cardlish_split_mvp/scripts/analyze_card_colors.py#L190-L207):
```python
# Ghi đè cho thẻ phụ âm (các thẻ từ 200 đến 299 mặc định là màu xám)
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
```

### Phòng tránh
> [!TIP]
> **Kết hợp suy luận logic nghiệp vụ (domain logic) với phân tích dữ liệu tự động.**
> 
> Đối với những nhóm thực thể có quy luật thiết kế cố định (như dải ID này luôn có màu xám), ta nên ưu tiên áp dụng rule-based check trước khi chạy các thuật toán heuristic/computer vision để đảm bảo tính chính xác tuyệt đối và tiết kiệm tài nguyên xử lý.

---

## Tổng hợp: Checklist trước khi fetch URL

```
1. □ URL trả về Content-Type gì?
   - text/html → parse HTML
   - audio/* → save binary  
   - image/* → save binary
   - application/json → parse JSON
   
2. □ Response có bị block không?
   - 200 → OK
   - 403/503 → bot protection
   - SSL error → TLS fingerprint bị chặn
   
3. □ Kiểm tra first bytes (magic number):
   - ID3 → MP3 audio
   - \xff\xfb → MP3 (no ID3 tag)
   - \x89PNG → PNG image
   - \xff\xd8 → JPEG image  
   - <!DOCTYPE → HTML
   - { → JSON
   
4. □ Test 1 file trước, verify bằng mắt, rồi mới batch
5. □ Dùng stream=True cho file lớn
6. □ Windows: set UTF-8 stdout
7. □ Rate limit: time.sleep() giữa requests
```

---

## Quick Reference: Magic Bytes

| Bytes (hex) | Format |
|------------|--------|
| `49 44 33` | MP3 (ID3 tag) |
| `ff fb` / `ff f3` / `ff f2` | MP3 (no ID3) |
| `89 50 4e 47` | PNG |
| `ff d8 ff` | JPEG |
| `52 49 46 46` | WAV/RIFF |
| `4f 67 67 53` | OGG |
| `66 4c 61 43` | FLAC |
| `25 50 44 46` | PDF |
| `50 4b 03 04` | ZIP |
| `3c 21 44 4f` | HTML (`<!DO`) |
| `7b` | JSON (`{`) |
