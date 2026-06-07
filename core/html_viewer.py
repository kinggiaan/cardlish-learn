import json
from dataclasses import asdict
from pathlib import Path
from typing import List
from core.pairing import CardPair

def make_html_viewer(pairs: List[CardPair], out_dir: Path) -> None:
    """Generate the premium interactive HTML viewer for the cards."""
    viewer_dir = out_dir / "viewer"
    viewer_dir.mkdir(parents=True, exist_ok=True)
    
    # Load vocabulary mapping
    vocab_path = Path("public/data/cards_vocab.json")
    vocab_data = {}
    if vocab_path.exists():
        try:
            with vocab_path.open("r", encoding="utf-8") as f:
                vocab_data = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load cards_vocab.json: {e}")
            
    data = []
    for p in pairs:
        p_dict = asdict(p)
        card_no = p_dict.get("card_no")
        if card_no:
            # Padded to 3 digits (e.g. '1' -> '001')
            card_no_padded = card_no.zfill(3) if card_no.isdigit() else card_no
            vocab_key = f"{card_no_padded}_card"
            p_dict["vocab"] = vocab_data.get(vocab_key, None)
        else:
            p_dict["vocab"] = None
        data.append(p_dict)
    
    html = f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Cardlish 3D Premium Viewer</title>
  <!-- Import Google Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  
  <style>
    :root {{
      --bg-gradient: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
      --card-bg: rgba(30, 41, 59, 0.7);
      --card-border: rgba(255, 255, 255, 0.08);
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #6366f1;
      --accent-hover: #4f46e5;
      --success: #10b981;
      --warning: #f59e0b;
      --font: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
      --card-min-w: 400px;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: var(--font);
      background: var(--bg-gradient);
      color: var(--text-main);
      min-height: 100vh;
      padding: 40px 20px;
      line-height: 1.5;
    }}

    .container {{
      max-width: 1800px;
      margin: 0 auto;
    }}

    header {{
      text-align: center;
      margin-bottom: 40px;
    }}

    h1 {{
      font-size: 2.5rem;
      font-weight: 700;
      letter-spacing: -0.025em;
      margin-bottom: 8px;
      background: linear-gradient(to right, #a5b4fc, #6366f1, #ec4899);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}

    .subtitle {{
      color: var(--text-muted);
      font-size: 1.05rem;
    }}

    /* Control Panel */
    .controls {{
      background: rgba(30, 41, 59, 0.45);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 20px;
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      margin-bottom: 30px;
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      align-items: center;
      justify-content: space-between;
      box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
    }}

    .search-group {{
      flex: 1;
      min-width: 280px;
      position: relative;
    }}

    .search-input {{
      width: 100%;
      padding: 12px 16px;
      border-radius: 10px;
      border: 1px solid var(--card-border);
      background: rgba(15, 23, 42, 0.6);
      color: var(--text-main);
      font-family: var(--font);
      font-size: 0.95rem;
      transition: all 0.2s;
    }}

    .search-input:focus {{
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
    }}

    .filter-group {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }}

    .btn {{
      padding: 10px 18px;
      border-radius: 10px;
      border: 1px solid var(--card-border);
      background: rgba(30, 41, 59, 0.6);
      color: var(--text-main);
      font-family: var(--font);
      font-size: 0.9rem;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s;
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }}

    .btn:hover {{
      background: rgba(51, 65, 85, 0.7);
      border-color: var(--text-muted);
    }}

    .btn.active {{
      background: var(--accent);
      border-color: var(--accent);
      box-shadow: 0 0 12px rgba(99, 102, 241, 0.4);
    }}

    .btn-action {{
      background: var(--accent);
      border-color: var(--accent);
    }}

    .btn-action:hover {{
      background: var(--accent-hover);
    }}

    .size-group {{
      display: flex;
      gap: 4px;
      background: rgba(15, 23, 42, 0.5);
      border-radius: 12px;
      padding: 4px;
      border: 1px solid var(--card-border);
    }}

    .size-group .btn {{
      padding: 8px 14px;
      border-radius: 8px;
      border: none;
      font-size: 0.8rem;
    }}

    /* Grid */
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(var(--card-min-w), 1fr));
      gap: 28px;
      transition: all 0.3s ease;
    }}

    /* Size modes */
    .grid.size-compact {{
      --card-min-w: 280px;
    }}
    .grid.size-normal {{
      --card-min-w: 400px;
    }}
    .grid.size-large {{
      --card-min-w: 550px;
    }}

    /* Card 3D Flip Container */
    .card-item {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 20px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      transition: transform 0.3s, box-shadow 0.3s;
    }}

    .card-item:hover {{
      transform: translateY(-4px);
      box-shadow: 0 15px 35px rgba(99, 102, 241, 0.15);
      border-color: rgba(99, 102, 241, 0.3);
    }}

    .card-view-wrapper {{
      perspective: 1200px;
      width: 100%;
      aspect-ratio: 63 / 88;  /* Standard playing card ratio */
    }}

    .card-inner {{
      position: relative;
      width: 100%;
      height: 100%;
      transform-style: preserve-3d;
      transition: transform 0.6s cubic-bezier(0.4, 0, 0.2, 1);
      cursor: pointer;
    }}

    .card-view-wrapper.is-flipped .card-inner {{
      transform: rotateY(180deg);
    }}

    .card-front, .card-back {{
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      backface-visibility: hidden;
      -webkit-backface-visibility: hidden;
      border-radius: 12px;
      overflow: hidden;
      background: #f5f5f0;  /* Light warm background to match card stock */
      border: 2px solid rgba(200, 190, 170, 0.4);
      box-shadow: inset 0 0 20px rgba(0,0,0,0.03);
    }}

    .card-front img, .card-back img {{
      width: 100%;
      height: 100%;
      object-fit: contain;  /* Show full image without cropping */
      padding: 2px;
    }}

    .card-back {{
      transform: rotateY(180deg);
    }}

    .side-label {{
      position: absolute;
      top: 8px;
      right: 8px;
      background: rgba(15, 23, 42, 0.75);
      padding: 4px 10px;
      border-radius: 20px;
      font-size: 0.75rem;
      font-weight: 500;
      backdrop-filter: blur(4px);
      -webkit-backdrop-filter: blur(4px);
      border: 1px solid rgba(255, 255, 255, 0.1);
    }}

    /* Card Meta */
    .card-meta {{
      display: flex;
      flex-direction: column;
      gap: 8px;
      flex-grow: 1;
    }}

    .card-title {{
      font-size: 1.2rem;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .cell-badge {{
      background: rgba(99, 102, 241, 0.15);
      color: #a5b4fc;
      border: 1px solid rgba(99, 102, 241, 0.3);
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 600;
    }}

    .card-details {{
      font-size: 0.85rem;
      color: var(--text-muted);
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}

    .card-actions {{
      display: flex;
      gap: 10px;
      margin-top: auto;
    }}

    .card-actions .btn {{
      flex: 1;
      justify-content: center;
      padding: 8px 12px;
      font-size: 0.85rem;
    }}

    .btn-qr {{
      border-color: rgba(16, 185, 129, 0.3);
      color: #a7f3d0;
      background: rgba(16, 185, 129, 0.1);
      text-decoration: none;
    }}

    .btn-qr:hover {{
      background: rgba(16, 185, 129, 0.2);
      border-color: var(--success);
    }}

    .status-warning {{
      background: rgba(245, 158, 11, 0.1);
      border: 1px solid rgba(245, 158, 11, 0.3);
      color: #fde68a;
      padding: 8px 12px;
      border-radius: 10px;
      font-size: 0.8rem;
    }}

    /* Lightbox */
    .lightbox {{
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(15, 23, 42, 0.92);
      backdrop-filter: blur(12px);
      display: none;
      justify-content: center;
      align-items: center;
      z-index: 1000;
      opacity: 0;
      transition: opacity 0.3s;
    }}

    .lightbox.show {{
      display: flex;
      opacity: 1;
    }}

    .lightbox-content {{
      position: relative;
      display: flex;
      gap: 24px;
      align-items: center;
      max-width: 95%;
      max-height: 90%;
    }}

    .lightbox-card {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 12px;
    }}

    .lightbox-card-label {{
      font-size: 1rem;
      font-weight: 600;
      color: var(--text-muted);
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }}

    .lightbox-img {{
      max-height: 78vh;
      max-width: 45vw;
      border-radius: 16px;
      border: 3px solid rgba(255, 255, 255, 0.12);
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
      background: #f5f5f0;
      object-fit: contain;
    }}

    .lightbox-divider {{
      width: 2px;
      height: 60vh;
      background: linear-gradient(to bottom, transparent, rgba(99, 102, 241, 0.4), transparent);
      border-radius: 2px;
    }}

    .lightbox-close {{
      position: fixed;
      top: 20px;
      right: 30px;
      background: rgba(30, 41, 59, 0.7);
      border: 1px solid var(--card-border);
      color: #fff;
      font-size: 1.5rem;
      cursor: pointer;
      width: 48px;
      height: 48px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s;
      z-index: 1001;
    }}

    .lightbox-close:hover {{
      background: rgba(99, 102, 241, 0.4);
      transform: scale(1.1);
    }}

    .lightbox-title {{
      position: fixed;
      top: 24px;
      left: 50%;
      transform: translateX(-50%);
      font-size: 1.3rem;
      font-weight: 600;
      color: var(--text-main);
      z-index: 1001;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Cardlish 3D Premium Viewer</h1>
      <p class="subtitle">Click vào ảnh hoặc nút "Lật thẻ" để xoay mặt 3D. Nhấp đúp để phóng to ảnh.</p>
    </header>

    <div class="controls">
      <div class="search-group">
        <input type="text" id="search" class="search-input" placeholder="Tìm kiếm theo Số thẻ hoặc Nhãn..." />
      </div>

      <div class="filter-group">
        <button class="btn active" id="btn-all-filter" onclick="filterCell('ALL')">Tất cả</button>
        <button class="btn" id="btn-col1" onclick="filterCol(1)">Cột 1</button>
        <button class="btn" id="btn-col2" onclick="filterCol(2)">Cột 2</button>
        <button class="btn" id="btn-col3" onclick="filterCol(3)">Cột 3</button>
        <button class="btn" id="btn-row1" onclick="filterRow(1)">Dòng 1</button>
        <button class="btn" id="btn-row2" onclick="filterRow(2)">Dòng 2</button>
        <button class="btn" id="btn-row3" onclick="filterRow(3)">Dòng 3</button>
      </div>

      <div class="size-group">
        <button class="btn" id="size-compact" onclick="setSize('compact')">Nhỏ</button>
        <button class="btn active" id="size-normal" onclick="setSize('normal')">Vừa</button>
        <button class="btn" id="size-large" onclick="setSize('large')">Lớn</button>
      </div>

      <div class="sort-group" style="display: flex; align-items: center; gap: 8px; background: rgba(15, 23, 42, 0.5); padding: 4px 10px; border-radius: 12px; border: 1px solid var(--card-border);">
        <label for="sort-select" style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Sắp xếp:</label>
        <select id="sort-select" class="btn" style="padding: 6px 12px; font-size: 0.85rem; border: none; background: transparent; cursor: pointer; outline: none;" onchange="handleSortChange()">
          <option value="card_no-asc" style="background: #1e293b;">Số thẻ (Tăng)</option>
          <option value="card_no-desc" style="background: #1e293b;">Số thẻ (Giảm)</option>
          <option value="date-desc" style="background: #1e293b;" selected>Mới nhất</option>
          <option value="date-asc" style="background: #1e293b;">Cũ nhất</option>
        </select>
      </div>

      <div class="export-group" style="display: flex; gap: 8px; flex-wrap: wrap;">
        <button class="btn" onclick="selectAllCards(true)">Chọn tất cả</button>
        <button class="btn" onclick="selectAllCards(false)">Bỏ chọn</button>
        <button class="btn btn-action" onclick="exportSelectedJSON()" style="background: var(--success); border-color: var(--success); box-shadow: 0 0 12px rgba(16, 185, 129, 0.4);">Xuất JSON (<span id="select-count">0</span>)</button>
        <button class="btn btn-action" onclick="flipAll()">Lật tất cả</button>
      </div>
    </div>

    <div class="grid size-normal" id="grid"></div>
  </div>

  <!-- Lightbox zoom: side-by-side front & back -->
  <div class="lightbox" id="lightbox" onclick="closeLightbox()">
    <span class="lightbox-title" id="lightbox-title"></span>
    <button class="lightbox-close" onclick="closeLightbox()">&times;</button>
    <div class="lightbox-content" onclick="event.stopPropagation()">
      <div class="lightbox-card">
        <span class="lightbox-card-label">Mặt trước</span>
        <img id="lightbox-front" class="lightbox-img" src="" alt="Front" />
      </div>
      <div class="lightbox-divider"></div>
      <div class="lightbox-card">
        <span class="lightbox-card-label">Mặt sau</span>
        <img id="lightbox-back" class="lightbox-img" src="" alt="Back" />
      </div>
    </div>
  </div>

<script>
const cards = {json.dumps(data, ensure_ascii=False)};
const grid = document.getElementById('grid');

// Build UI
function initGrid() {{
  grid.innerHTML = '';
  cards.forEach((c, index) => {{
    const item = document.createElement('div');
    item.className = 'card-item';
    item.id = `card-item-${{index}}`;
    item.setAttribute('data-no', c.card_no || '');
    item.setAttribute('data-label', c.label || '');
    item.setAttribute('data-cell', c.cell || '');
    item.setAttribute('data-row', c.row || '');
    item.setAttribute('data-col', c.col || '');
    
    // Plain text for searching
    let vocabSearchText = '';
    let vocabHtml = '';
    if (c.vocab) {{
      const frontWords = (c.vocab.front || []).map(w => `${{w.word}} <span style="color:var(--text-muted); font-size:0.8rem;">${{w.ipa}}</span>`).join(', ');
      const backWords = (c.vocab.back || []).map(w => `${{w.word}} <span style="color:var(--text-muted); font-size:0.8rem;">${{w.ipa}}</span>`).join(', ');
      
      const frontSentEn = (c.vocab.front_sentences || []).map(s => s.en).join('<br>');
      const frontSentVi = (c.vocab.front_sentences || []).map(s => s.vi).join('<br>');
      
      const backSentEn = (c.vocab.back_sentences || []).map(s => s.en).join('<br>');
      const backSentVi = (c.vocab.back_sentences || []).map(s => s.vi).join('<br>');
      
      const searchFrontWords = (c.vocab.front || []).map(w => w.word).join(' ');
      const searchBackWords = (c.vocab.back || []).map(w => w.word).join(' ');
      const searchFrontSents = (c.vocab.front_sentences || []).map(s => s.en + ' ' + s.vi).join(' ');
      const searchBackSents = (c.vocab.back_sentences || []).map(s => s.en + ' ' + s.vi).join(' ');
      vocabSearchText = `${{searchFrontWords}} ${{searchBackWords}} ${{searchFrontSents}} ${{searchBackSents}}`.toLowerCase();
      
      vocabHtml = `
        <div class="card-vocab" style="margin-top: 12px; border-top: 1px dashed rgba(255,255,255,0.15); padding-top: 10px; display: flex; flex-direction: column; gap: 10px;">
          ${{frontWords ? `
          <div>
            <span style="color: #a5b4fc; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; display: block; margin-bottom: 2px;">Mặt trước (Front)</span>
            <div style="font-size: 0.95rem; color: var(--text-main); font-weight: 500;">${{frontWords}}</div>
            ${{frontSentEn ? `<div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 4px; line-height: 1.3;">${{frontSentEn}}<br><span style="color: rgba(148,163,184,0.7); font-size: 0.78rem;">${{frontSentVi}}</span></div>` : ''}}
          </div>
          ` : ''}}
          
          ${{backWords ? `
          <div>
            <span style="color: #ec4899; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; display: block; margin-bottom: 2px;">Mặt sau (Back)</span>
            <div style="font-size: 0.95rem; color: var(--text-main); font-weight: 500;">${{backWords}}</div>
            ${{backSentEn ? `<div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 4px; line-height: 1.3;">${{backSentEn}}<br><span style="color: rgba(148,163,184,0.7); font-size: 0.78rem;">${{backSentVi}}</span></div>` : ''}}
          </div>
          ` : ''}}
        </div>
      `;
    }}
    item.setAttribute('data-vocab', vocabSearchText);
    
    // 3D wrapper
    const wrapper = document.createElement('div');
    wrapper.className = 'card-view-wrapper';
    wrapper.id = `wrapper-${{index}}`;
    
    const inner = document.createElement('div');
    inner.className = 'card-inner';
    inner.onclick = () => toggleFlip(index);
    inner.ondblclick = () => openLightbox(c);
    
    const front = document.createElement('div');
    front.className = 'card-front';
    const imgFront = document.createElement('img');
    imgFront.src = '../' + c.front_image;
    imgFront.loading = 'lazy';
    const labelFront = document.createElement('span');
    labelFront.className = 'side-label';
    labelFront.textContent = 'Mặt trước';
    front.append(imgFront, labelFront);
    
    const back = document.createElement('div');
    back.className = 'card-back';
    const imgBack = document.createElement('img');
    imgBack.src = '../' + c.back_image;
    imgBack.loading = 'lazy';
    const labelBack = document.createElement('span');
    labelBack.className = 'side-label';
    labelBack.textContent = 'Mặt sau';
    back.append(imgBack, labelBack);
    
    inner.append(front, back);
    wrapper.append(inner);
    
    // Meta block
    const meta = document.createElement('div');
    meta.className = 'card-meta';
    
    const title = document.createElement('h3');
    title.className = 'card-title';
    title.style.display = 'flex';
    title.style.alignItems = 'center';
    title.style.gap = '10px';
    
    const isChecked = selectedPairIds.has(c.pair_id) ? 'checked' : '';
    title.innerHTML = `
      <input type="checkbox" class="card-select" data-id="${{c.pair_id}}" ${{isChecked}} style="width: 18px; height: 18px; cursor: pointer;" onclick="event.stopPropagation();" onchange="toggleSelect('${{c.pair_id}}', this.checked)" />
      <span>${{c.card_no ? '#' + c.card_no : 'Thẻ'}} ${{c.label ? ' - ' + c.label : ''}}</span>
      <span class="cell-badge">${{c.cell}}</span>
    `;
    
    const details = document.createElement('div');
    details.className = 'card-details';
    details.innerHTML = `
      <span>Tọa độ ô: Dòng ${{c.row}}, Cột ${{c.col}}</span>
      <span>Nguồn: Trang trước p${{c.front_page}} / Trang sau p${{c.back_page}}</span>
      <span>Ngày tách: ${{c.created_at || '04/06/2026'}}</span>
    `;
    
    meta.append(title, details);
    
    if (vocabHtml) {{
      const vocabDiv = document.createElement('div');
      vocabDiv.innerHTML = vocabHtml;
      meta.append(vocabDiv);
    }}
    
    if (c.needs_review) {{
      const warning = document.createElement('div');
      warning.className = 'status-warning';
      warning.textContent = c.review_note || 'Cần kiểm tra lại mặt trước/sau';
      meta.append(warning);
    }}
    
    // Actions block
    const actions = document.createElement('div');
    actions.className = 'card-actions';
    
    if (c.qr_url) {{
      const qrBtn = document.createElement('a');
      qrBtn.className = 'btn btn-qr';
      qrBtn.href = c.qr_url;
      qrBtn.target = '_blank';
      qrBtn.textContent = 'Link QR';
      actions.append(qrBtn);
    }}
    
    const flipBtn = document.createElement('button');
    flipBtn.className = 'btn';
    flipBtn.textContent = 'Lật thẻ';
    flipBtn.onclick = (e) => {{
      e.stopPropagation();
      toggleFlip(index);
    }};
    
    actions.append(flipBtn);
    
    item.append(wrapper, meta, actions);
    grid.appendChild(item);
  }});
}}

function toggleFlip(index) {{
  const wrapper = document.getElementById(`wrapper-${{index}}`);
  wrapper.classList.toggle('is-flipped');
}}

// Flip all cards with staggered delay
let allFlipped = false;
function flipAll() {{
  allFlipped = !allFlipped;
  const wrappers = document.querySelectorAll('.card-view-wrapper');
  wrappers.forEach((el, i) => {{
    setTimeout(() => {{
      if (allFlipped) {{
        el.classList.add('is-flipped');
      }} else {{
        el.classList.remove('is-flipped');
      }}
    }}, i * 50); // 50ms stagger
  }});
}}

// Card size control
function setSize(size) {{
  const grid = document.getElementById('grid');
  grid.className = 'grid size-' + size;
  document.querySelectorAll('.size-group .btn').forEach(b => b.classList.remove('active'));
  document.getElementById('size-' + size).classList.add('active');
}}

// Lightbox control — shows both front & back side-by-side
function openLightbox(card) {{
  const lb = document.getElementById('lightbox');
  document.getElementById('lightbox-front').src = '../' + card.front_image;
  document.getElementById('lightbox-back').src = '../' + card.back_image;
  const title = (card.card_no ? '#' + card.card_no : 'Thẻ') + (card.label ? ' — ' + card.label : '');
  document.getElementById('lightbox-title').textContent = title;
  lb.classList.add('show');
}}

function closeLightbox() {{
  document.getElementById('lightbox').classList.remove('show');
}}

// Filter logic
let currentFilterType = 'ALL'; // ALL, ROW, COL
let currentFilterVal = null;

function clearFilterButtons() {{
  document.querySelectorAll('.filter-group .btn').forEach(btn => btn.classList.remove('active'));
}}

function filterCell(type) {{
  clearFilterButtons();
  document.getElementById('btn-all-filter').classList.add('active');
  currentFilterType = 'ALL';
  currentFilterVal = null;
  applyFilter();
}}

function filterCol(colVal) {{
  clearFilterButtons();
  document.getElementById(`btn-col${{colVal}}`).classList.add('active');
  currentFilterType = 'COL';
  currentFilterVal = colVal.toString();
  applyFilter();
}}

function filterRow(rowVal) {{
  clearFilterButtons();
  document.getElementById(`btn-row${{rowVal}}`).classList.add('active');
  currentFilterType = 'ROW';
  currentFilterVal = rowVal.toString();
  applyFilter();
}}

function applyFilter() {{
  const query = document.getElementById('search').value.toLowerCase().trim() || '';
  const cardItems = document.querySelectorAll('.card-item');
  
  cardItems.forEach(item => {{
    const no = item.getAttribute('data-no').toLowerCase();
    const label = item.getAttribute('data-label').toLowerCase();
    const cell = item.getAttribute('data-cell').toLowerCase();
    const row = item.getAttribute('data-row');
    const col = item.getAttribute('data-col');
    const vocab = (item.getAttribute('data-vocab') || '').toLowerCase();
    
    // Search check
    const matchesSearch = !query || no.includes(query) || label.includes(query) || cell.includes(query) || vocab.includes(query);
    
    // Layout filter check
    let matchesLayout = true;
    if (currentFilterType === 'ROW') {{
      matchesLayout = (row === currentFilterVal);
    }} else if (currentFilterType === 'COL') {{
      matchesLayout = (col === currentFilterVal);
    }}
    
    if (matchesSearch && matchesLayout) {{
      item.style.display = 'flex';
    }} else {{
      item.style.display = 'none';
    }}
  }});
}}

function parseDate(dateStr) {{
  if (!dateStr) return new Date(2026, 5, 4);
  const parts = dateStr.split('/');
  if (parts.length === 3) {{
    return new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0]));
  }}
  return new Date(2026, 5, 4);
}}

function handleSortChange() {{
  const sortVal = document.getElementById('sort-select').value;
  
  if (sortVal === 'card_no-asc') {{
    cards.sort((a, b) => {{
      const numA = parseInt(String(a.card_no).replace(/\D/g, ''), 10) || 9999;
      const numB = parseInt(String(b.card_no).replace(/\D/g, ''), 10) || 9999;
      return numA - numB;
    }});
  }} else if (sortVal === 'card_no-desc') {{
    cards.sort((a, b) => {{
      const numA = parseInt(String(a.card_no).replace(/\D/g, ''), 10) || 9999;
      const numB = parseInt(String(b.card_no).replace(/\D/g, ''), 10) || 9999;
      return numB - numA;
    }});
  }} else if (sortVal === 'date-desc') {{
    cards.sort((a, b) => {{
      return parseDate(b.created_at) - parseDate(a.created_at) || (parseInt(a.card_no) - parseInt(b.card_no));
    }});
  }} else if (sortVal === 'date-asc') {{
    cards.sort((a, b) => {{
      return parseDate(a.created_at) - parseDate(b.created_at) || (parseInt(a.card_no) - parseInt(b.card_no));
    }});
  }}
  
  initGrid();
  applyFilter();
}}

const selectedPairIds = new Set();

function toggleSelect(pairId, checked) {{
  if (checked) {{
    selectedPairIds.add(pairId);
  }} else {{
    selectedPairIds.delete(pairId);
  }}
  updateSelectCount();
}}

function updateSelectCount() {{
  document.getElementById('select-count').textContent = selectedPairIds.size;
}}

function selectAllCards(select) {{
  const cardItems = document.querySelectorAll('.card-item');
  cardItems.forEach(item => {{
    if (item.style.display !== 'none') {{
      const cb = item.querySelector('.card-select');
      if (cb) {{
        const pairId = cb.getAttribute('data-id');
        cb.checked = select;
        if (select) {{
          selectedPairIds.add(pairId);
        }} else {{
          selectedPairIds.delete(pairId);
        }}
      }}
    }}
  }});
  updateSelectCount();
}}

function exportSelectedJSON() {{
  if (selectedPairIds.size === 0) {{
    alert('Vui lòng chọn ít nhất một thẻ để xuất JSON!');
    return;
  }}
  
  const selectedCards = cards.filter(c => selectedPairIds.has(c.pair_id));
  const jsonStr = JSON.stringify(selectedCards, null, 2);
  
  const blob = new Blob([jsonStr], {{ type: 'application/json' }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `cardlish_selected_${{selectedCards.length}}_cards.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}}

document.getElementById('search').addEventListener('input', applyFilter);

// Initialize
handleSortChange();
</script>
</body>
</html>
"""
    (viewer_dir / "index.html").write_text(html, encoding="utf-8")
