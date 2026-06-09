/* ═══════════════════════════════════════════════════════════
   Cardlish Review Editor — Core Logic
   ═══════════════════════════════════════════════════════════ */

// ── Data Sources (relative to admin/) ────────────────────
const DATA_SOURCES = {
    cardsJson: '../public/data/cards.json',
    manifest: '../unified_db/data/cards_manifest.json',
    overrides: '../unified_db/data/review_overrides.json',
};
const IMAGE_BASE = '../unified_db/';
const AUDIO_BASE = '../public/';

// ── State ────────────────────────────────────────────────
const state = {
    cards: [],           // merged card data
    filtered: [],        // cards after filter/search/sort
    overrides: {},       // loaded overrides from file
    pendingChanges: {},  // pair_id → {field: newValue} (unsaved edits)
    selectedIndex: -1,   // index in filtered[]
    activeFilter: 'all',
    searchQuery: '',
    sortBy: 'card_no',
    audio: null,         // shared Audio element
};

// ── DOM Cache ────────────────────────────────────────────
const dom = {};
function cacheDom() {
    dom.cardGrid = document.getElementById('card-grid');
    dom.cardListEmpty = document.getElementById('card-list-empty');
    dom.detailEmpty = document.getElementById('detail-empty');
    dom.detailContent = document.getElementById('detail-content');
    dom.frontImg = document.getElementById('detail-front-img');
    dom.backImg = document.getElementById('detail-back-img');
    dom.frontPlaceholder = document.getElementById('front-placeholder');
    dom.backPlaceholder = document.getElementById('back-placeholder');
    dom.infoPairId = document.getElementById('info-pair-id');
    dom.infoCell = document.getElementById('info-cell');
    dom.infoPages = document.getElementById('info-pages');
    dom.infoDate = document.getElementById('info-date');
    dom.infoAudio = document.getElementById('info-audio');
    dom.editCardNo = document.getElementById('edit-card-no');
    dom.editLabel = document.getElementById('edit-label');
    dom.editQrUrl = document.getElementById('edit-qr-url');
    dom.editNote = document.getElementById('edit-note');
    dom.dotCardNo = document.getElementById('dot-card-no');
    dom.dotLabel = document.getElementById('dot-label');
    dom.dotQrUrl = document.getElementById('dot-qr-url');
    dom.dotNote = document.getElementById('dot-note');
    dom.btnReviewed = document.getElementById('btn-reviewed');
    dom.btnSwap = document.getElementById('btn-swap');
    dom.btnLock = document.getElementById('btn-lock');
    dom.btnAudio = document.getElementById('btn-audio');
    dom.btnRevert = document.getElementById('btn-revert');
    dom.btnSaveNext = document.getElementById('btn-save-next');
    dom.btnExport = document.getElementById('btn-export');
    dom.btnImport = document.getElementById('btn-import');
    dom.importFileInput = document.getElementById('import-file-input');
    dom.searchInput = document.getElementById('search-input');
    dom.sortSelect = document.getElementById('sort-select');
    dom.zoomOverlay = document.getElementById('zoom-overlay');
    dom.zoomFront = document.getElementById('zoom-front');
    dom.zoomBack = document.getElementById('zoom-back');
    dom.toastContainer = document.getElementById('toast-container');
    dom.statTotal = document.querySelector('#stat-total strong');
    dom.statReview = document.querySelector('#stat-review strong');
    dom.statBatch = document.querySelector('#stat-batch strong');
    dom.statLocked = document.querySelector('#stat-locked strong');
    dom.statChanges = document.querySelector('#stat-changes strong');
}

// ── Data Loading ─────────────────────────────────────────
async function loadData() {
    try {
        // Load cards.json (primary, enriched data)
        const cardsRes = await fetch(DATA_SOURCES.cardsJson);
        if (!cardsRes.ok) throw new Error(`Failed to load cards.json: ${cardsRes.status}`);
        state.cards = await cardsRes.json();

        // Load overrides (optional)
        try {
            const ovRes = await fetch(DATA_SOURCES.overrides);
            if (ovRes.ok) {
                const ovData = await ovRes.json();
                state.overrides = ovData.overrides || {};
                // Apply loaded overrides to cards
                for (const card of state.cards) {
                    const ov = state.overrides[card.pair_id];
                    if (ov) {
                        for (const [key, val] of Object.entries(ov)) {
                            card[key] = val;
                        }
                    }
                }
            }
        } catch (e) {
            console.log('No existing overrides found');
        }

        applyFilterAndSort();
        renderCardGrid();
        updateStats();
        toast(`Loaded ${state.cards.length} cards`, 'success');
    } catch (err) {
        toast(`Error loading data: ${err.message}`, 'error');
        console.error(err);
    }
}

// ── Filtering & Sorting ──────────────────────────────────
function applyFilterAndSort() {
    let cards = [...state.cards];
    const q = state.searchQuery.toLowerCase().trim();

    // Filter
    switch (state.activeFilter) {
        case 'needs_review':
            cards = cards.filter(c => c.needs_review);
            break;
        case 'batch':
            cards = cards.filter(c => c.pair_id.startsWith('batch'));
            break;
        case 'locked':
            cards = cards.filter(c => c.manual_locked);
            break;
        case 'reviewed':
            cards = cards.filter(c => !c.needs_review && !c.pair_id.startsWith('batch'));
            break;
    }

    // Search
    if (q) {
        cards = cards.filter(c =>
            (c.pair_id || '').toLowerCase().includes(q) ||
            (c.card_no || '').toLowerCase().includes(q) ||
            (c.label || '').toLowerCase().includes(q) ||
            (c.review_note || '').toLowerCase().includes(q) ||
            (c.qr_url || '').toLowerCase().includes(q)
        );
    }

    // Sort
    switch (state.sortBy) {
        case 'card_no':
            cards.sort((a, b) => {
                const an = parseInt(a.card_no) || 9999;
                const bn = parseInt(b.card_no) || 9999;
                return an - bn || a.pair_id.localeCompare(b.pair_id);
            });
            break;
        case 'status':
            cards.sort((a, b) => {
                const sa = getStatusPriority(a);
                const sb = getStatusPriority(b);
                return sa - sb || a.pair_id.localeCompare(b.pair_id);
            });
            break;
        case 'date':
            cards.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
            break;
    }

    state.filtered = cards;
}

function getStatusPriority(card) {
    if (card.pair_id.startsWith('batch')) return 0;
    if (card.needs_review) return 1;
    if (card.manual_locked) return 3;
    return 2;
}

function getStatusClass(card) {
    if (card.hidden) return 'hidden';
    if (card.pair_id.startsWith('batch')) return 'batch';
    if (card.needs_review) return 'review';
    if (card.manual_locked) return 'locked';
    return 'ok';
}

// ── Card Grid Rendering ──────────────────────────────────
function renderCardGrid() {
    const fragment = document.createDocumentFragment();

    state.filtered.forEach((card, i) => {
        const div = document.createElement('div');
        div.className = 'card-thumb';
        if (i === state.selectedIndex) div.classList.add('active');
        if (state.pendingChanges[card.pair_id]) div.classList.add('has-changes');
        div.dataset.index = i;
        div.style.animationDelay = `${Math.min(i * 20, 500)}ms`;

        const statusClass = getStatusClass(card);
        const imgSrc = card.front_image ? IMAGE_BASE + card.front_image : '';
        const displayNo = card.card_no || card.pair_id.slice(0, 12);
        const labelText = card.label || '';

        div.innerHTML = `
            <span class="status-badge ${statusClass}"></span>
            <img class="card-thumb-img" src="${imgSrc}" alt="${card.pair_id}" loading="lazy"
                 onerror="this.classList.add('error')">
            <div class="card-thumb-placeholder">${card.pair_id}</div>
            <div class="card-thumb-meta">
                <span class="card-thumb-no">${escHtml(displayNo)}</span>
                <span class="card-thumb-label">${escHtml(labelText)}</span>
            </div>
        `;

        div.addEventListener('click', () => selectCard(i));
        fragment.appendChild(div);
    });

    dom.cardGrid.innerHTML = '';
    dom.cardGrid.appendChild(fragment);
    dom.cardListEmpty.style.display = state.filtered.length === 0 ? 'flex' : 'none';
}

// ── Card Selection & Detail ──────────────────────────────
function selectCard(index) {
    if (index < 0 || index >= state.filtered.length) return;

    // Save current edits before switching
    if (state.selectedIndex >= 0) saveCurrentEdits();

    state.selectedIndex = index;
    const card = state.filtered[index];

    // Update grid highlight
    document.querySelectorAll('.card-thumb.active').forEach(el => el.classList.remove('active'));
    const thumb = dom.cardGrid.children[index];
    if (thumb) {
        thumb.classList.add('active');
        thumb.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // Show detail
    dom.detailEmpty.style.display = 'none';
    dom.detailContent.style.display = 'block';
    dom.detailContent.style.animation = 'slideInRight 0.25s ease';

    // Images
    setImage(dom.frontImg, dom.frontPlaceholder, card.front_image);
    setImage(dom.backImg, dom.backPlaceholder, card.back_image);

    // Info chips
    dom.infoPairId.textContent = card.pair_id;
    dom.infoCell.textContent = `Cell: ${card.cell || '?'}`;
    dom.infoPages.textContent = `Pages: ${card.front_page ?? '?'}/${card.back_page ?? '?'}`;
    dom.infoDate.textContent = card.created_at || '';
    const audioStatus = card.audio?.status || 'none';
    dom.infoAudio.textContent = `Audio: ${audioStatus}`;
    dom.infoAudio.style.display = audioStatus === 'none' ? 'none' : '';

    // Editable fields — use pending changes if any, otherwise card data
    const pending = state.pendingChanges[card.pair_id] || {};
    dom.editCardNo.value = pending.card_no ?? card.card_no ?? '';
    dom.editLabel.value = pending.label ?? card.label ?? '';
    dom.editQrUrl.value = pending.qr_url ?? card.qr_url ?? '';
    dom.editNote.value = pending.review_note ?? card.review_note ?? '';

    // Update change dots
    updateChangeDots(card);

    // Update lock button text
    const isLocked = pending.manual_locked ?? card.manual_locked;
    dom.btnLock.innerHTML = isLocked ? '🔓 Unlock' : '🔒 Lock';

    // Audio button
    dom.btnAudio.style.display = (card.audio?.status === 'downloaded') ? '' : 'none';
}

function setImage(imgEl, placeholderEl, imagePath) {
    if (imagePath) {
        imgEl.src = IMAGE_BASE + imagePath;
        imgEl.style.display = 'block';
        placeholderEl.style.display = 'none';
        imgEl.onerror = () => {
            imgEl.style.display = 'none';
            placeholderEl.style.display = 'flex';
        };
    } else {
        imgEl.style.display = 'none';
        placeholderEl.style.display = 'flex';
    }
}

function updateChangeDots(card) {
    const pending = state.pendingChanges[card.pair_id] || {};
    toggleDot(dom.dotCardNo, pending.card_no !== undefined && pending.card_no !== (card.card_no ?? ''));
    toggleDot(dom.dotLabel, pending.label !== undefined && pending.label !== (card.label ?? ''));
    toggleDot(dom.dotQrUrl, pending.qr_url !== undefined && pending.qr_url !== (card.qr_url ?? ''));
    toggleDot(dom.dotNote, pending.review_note !== undefined && pending.review_note !== (card.review_note ?? ''));
}

function toggleDot(dotEl, visible) {
    dotEl.classList.toggle('visible', visible);
}

// ── Edit Tracking ────────────────────────────────────────
function saveCurrentEdits() {
    if (state.selectedIndex < 0) return;
    const card = state.filtered[state.selectedIndex];
    if (!card) return;

    const newCardNo = dom.editCardNo.value.trim();
    const newLabel = dom.editLabel.value.trim();
    const newQrUrl = dom.editQrUrl.value.trim();
    const newNote = dom.editNote.value.trim();

    const changes = {};
    if (newCardNo !== (card.card_no ?? '')) changes.card_no = newCardNo;
    if (newLabel !== (card.label ?? '')) changes.label = newLabel;
    if (newQrUrl !== (card.qr_url ?? '')) changes.qr_url = newQrUrl;
    if (newNote !== (card.review_note ?? '')) changes.review_note = newNote;

    // Merge with existing pending
    const existing = state.pendingChanges[card.pair_id] || {};
    const merged = { ...existing, ...changes };

    // Remove changes that match original
    for (const key of Object.keys(merged)) {
        if (merged[key] === (card[key] ?? '')) delete merged[key];
    }

    if (Object.keys(merged).length > 0) {
        state.pendingChanges[card.pair_id] = merged;
    } else {
        delete state.pendingChanges[card.pair_id];
    }

    updateStats();
    // Update thumb highlight
    const thumb = dom.cardGrid.children[state.selectedIndex];
    if (thumb) {
        thumb.classList.toggle('has-changes', !!state.pendingChanges[card.pair_id]);
    }
}

// ── Actions ──────────────────────────────────────────────
function markReviewed() {
    if (state.selectedIndex < 0) return;
    const card = state.filtered[state.selectedIndex];
    const pending = state.pendingChanges[card.pair_id] || {};
    pending.needs_review = false;
    pending.manual_locked = true;
    state.pendingChanges[card.pair_id] = pending;
    card.needs_review = false;
    card.manual_locked = true;
    dom.btnLock.innerHTML = '🔓 Unlock';
    updateStats();
    renderCardGrid();
    toast(`✅ ${card.pair_id} marked as reviewed`, 'success');
}

function swapFaces() {
    if (state.selectedIndex < 0) return;
    const card = state.filtered[state.selectedIndex];
    const pending = state.pendingChanges[card.pair_id] || {};

    // Swap the actual card data
    const tmpFront = card.front_image;
    card.front_image = card.back_image;
    card.back_image = tmpFront;

    // Record in pending
    pending.front_image = card.front_image;
    pending.back_image = card.back_image;
    pending._swap_faces = true;
    state.pendingChanges[card.pair_id] = pending;

    // Update display
    setImage(dom.frontImg, dom.frontPlaceholder, card.front_image);
    setImage(dom.backImg, dom.backPlaceholder, card.back_image);
    updateStats();
    renderCardGrid();
    toast(`🔁 ${card.pair_id} front/back swapped`, 'info');
}

function toggleLock() {
    if (state.selectedIndex < 0) return;
    const card = state.filtered[state.selectedIndex];
    const pending = state.pendingChanges[card.pair_id] || {};
    const isLocked = pending.manual_locked ?? card.manual_locked;
    const newLocked = !isLocked;

    pending.manual_locked = newLocked;
    state.pendingChanges[card.pair_id] = pending;
    card.manual_locked = newLocked;

    dom.btnLock.innerHTML = newLocked ? '🔓 Unlock' : '🔒 Lock';
    updateStats();
    renderCardGrid();
    toast(newLocked ? `🔒 ${card.pair_id} locked` : `🔓 ${card.pair_id} unlocked`, 'info');
}

function playAudio() {
    if (state.selectedIndex < 0) return;
    const card = state.filtered[state.selectedIndex];
    if (card.audio?.status !== 'downloaded' || !card.audio.local_path) return;

    if (!state.audio) state.audio = new Audio();
    state.audio.src = AUDIO_BASE + card.audio.local_path;
    state.audio.play().catch(e => toast('Audio error: ' + e.message, 'error'));
}

function revertChanges() {
    if (state.selectedIndex < 0) return;
    const card = state.filtered[state.selectedIndex];
    delete state.pendingChanges[card.pair_id];

    // Reload original from overrides
    const ov = state.overrides[card.pair_id];
    if (ov) {
        for (const [key, val] of Object.entries(ov)) card[key] = val;
    }

    selectCard(state.selectedIndex);
    updateStats();
    renderCardGrid();
    toast(`↩️ ${card.pair_id} changes reverted`, 'info');
}

function saveAndNext() {
    saveCurrentEdits();

    // Find next error card
    const currentPairId = state.selectedIndex >= 0 ? state.filtered[state.selectedIndex]?.pair_id : null;
    let nextIndex = -1;

    for (let i = state.selectedIndex + 1; i < state.filtered.length; i++) {
        const c = state.filtered[i];
        if (c.needs_review || c.pair_id.startsWith('batch')) {
            nextIndex = i;
            break;
        }
    }

    // Wrap around
    if (nextIndex === -1) {
        for (let i = 0; i < state.selectedIndex; i++) {
            const c = state.filtered[i];
            if (c.needs_review || c.pair_id.startsWith('batch')) {
                nextIndex = i;
                break;
            }
        }
    }

    if (nextIndex >= 0) {
        selectCard(nextIndex);
    } else {
        toast('🎉 All cards reviewed! No more errors.', 'success');
    }
}

// ── Export / Import ──────────────────────────────────────
function exportPatch() {
    saveCurrentEdits();

    const overrides = {};
    let count = 0;

    for (const [pairId, changes] of Object.entries(state.pendingChanges)) {
        // Clean up internal flags
        const clean = { ...changes };
        delete clean._swap_faces;
        if (Object.keys(clean).length > 0) {
            overrides[pairId] = clean;
            count++;
        }
    }

    if (count === 0) {
        toast('No changes to export', 'info');
        return;
    }

    const patch = {
        _version: 1,
        _exported_at: new Date().toISOString(),
        _total_changes: count,
        overrides: overrides,
    };

    const blob = new Blob([JSON.stringify(patch, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `review_patch_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);

    toast(`📤 Exported ${count} change(s)`, 'success');
}

function importOverrides() {
    dom.importFileInput.click();
}

function handleImportFile(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        try {
            const data = JSON.parse(e.target.result);
            const overrides = data.overrides || {};
            let count = 0;

            for (const [pairId, fields] of Object.entries(overrides)) {
                const existing = state.pendingChanges[pairId] || {};
                state.pendingChanges[pairId] = { ...existing, ...fields };

                // Also apply to card data for display
                const card = state.cards.find(c => c.pair_id === pairId);
                if (card) {
                    for (const [k, v] of Object.entries(fields)) card[k] = v;
                }
                count++;
            }

            applyFilterAndSort();
            renderCardGrid();
            updateStats();
            if (state.selectedIndex >= 0) selectCard(state.selectedIndex);
            toast(`📥 Imported ${count} override(s)`, 'success');
        } catch (err) {
            toast(`Import error: ${err.message}`, 'error');
        }
    };
    reader.readAsText(file);
    event.target.value = '';
}

// ── Zoom ─────────────────────────────────────────────────
function openZoom(side) {
    if (state.selectedIndex < 0) return;
    const card = state.filtered[state.selectedIndex];

    dom.zoomFront.src = card.front_image ? IMAGE_BASE + card.front_image : '';
    dom.zoomBack.src = card.back_image ? IMAGE_BASE + card.back_image : '';
    dom.zoomOverlay.style.display = 'flex';
}

function closeZoom() {
    dom.zoomOverlay.style.display = 'none';
}

// ── Stats ────────────────────────────────────────────────
function updateStats() {
    const total = state.cards.length;
    const review = state.cards.filter(c => c.needs_review).length;
    const batch = state.cards.filter(c => c.pair_id.startsWith('batch')).length;
    const locked = state.cards.filter(c => c.manual_locked).length;
    const changes = Object.keys(state.pendingChanges).length;

    dom.statTotal.textContent = total;
    dom.statReview.textContent = review;
    dom.statBatch.textContent = batch;
    dom.statLocked.textContent = locked;
    dom.statChanges.textContent = changes;
}

// ── Toast ────────────────────────────────────────────────
function toast(msg, type = 'info') {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = msg;
    dom.toastContainer.appendChild(el);

    setTimeout(() => {
        el.classList.add('toast-out');
        setTimeout(() => el.remove(), 300);
    }, 3000);
}

// ── Utilities ────────────────────────────────────────────
function escHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ── Event Setup ──────────────────────────────────────────
function setupEvents() {
    // Filter tabs
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab.active').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            state.activeFilter = tab.dataset.filter;
            state.selectedIndex = -1;
            applyFilterAndSort();
            renderCardGrid();
            dom.detailEmpty.style.display = 'flex';
            dom.detailContent.style.display = 'none';
        });
    });

    // Search
    dom.searchInput.addEventListener('input', () => {
        state.searchQuery = dom.searchInput.value;
        state.selectedIndex = -1;
        applyFilterAndSort();
        renderCardGrid();
    });

    // Sort
    dom.sortSelect.addEventListener('change', () => {
        state.sortBy = dom.sortSelect.value;
        applyFilterAndSort();
        renderCardGrid();
    });

    // Action buttons
    dom.btnReviewed.addEventListener('click', markReviewed);
    dom.btnSwap.addEventListener('click', swapFaces);
    dom.btnLock.addEventListener('click', toggleLock);
    dom.btnAudio.addEventListener('click', playAudio);
    dom.btnRevert.addEventListener('click', revertChanges);
    dom.btnSaveNext.addEventListener('click', saveAndNext);
    dom.btnExport.addEventListener('click', exportPatch);
    dom.btnImport.addEventListener('click', importOverrides);
    dom.importFileInput.addEventListener('change', handleImportFile);

    // Zoom
    document.getElementById('front-image-wrap').addEventListener('click', () => openZoom('front'));
    document.getElementById('back-image-wrap').addEventListener('click', () => openZoom('back'));
    dom.zoomOverlay.addEventListener('click', closeZoom);

    // Field change tracking
    [dom.editCardNo, dom.editLabel, dom.editQrUrl, dom.editNote].forEach(el => {
        el.addEventListener('input', () => {
            if (state.selectedIndex >= 0) {
                const card = state.filtered[state.selectedIndex];
                updateChangeDots(card);
            }
        });
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Don't intercept when typing in inputs
        const isInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName);

        if (e.key === '/' && !isInput) {
            e.preventDefault();
            dom.searchInput.focus();
            return;
        }

        if (e.key === 'Escape') {
            if (dom.zoomOverlay.style.display !== 'none') {
                closeZoom();
            } else {
                dom.searchInput.blur();
            }
            return;
        }

        if (e.key === 'ArrowLeft' && !isInput) {
            e.preventDefault();
            if (state.selectedIndex > 0) selectCard(state.selectedIndex - 1);
            return;
        }

        if (e.key === 'ArrowRight' && !isInput) {
            e.preventDefault();
            if (state.selectedIndex < state.filtered.length - 1) selectCard(state.selectedIndex + 1);
            return;
        }

        if (e.key === 'Enter' && !isInput) {
            e.preventDefault();
            saveAndNext();
            return;
        }

        if (e.ctrlKey || e.metaKey) {
            if (e.key === 'r' || e.key === 'R') {
                e.preventDefault();
                markReviewed();
                return;
            }
            if (e.key === 'l' || e.key === 'L') {
                e.preventDefault();
                toggleLock();
                return;
            }
            if (e.key === 's' || e.key === 'S') {
                e.preventDefault();
                exportPatch();
                return;
            }
            if (e.key === 'f' || e.key === 'F') {
                if (!isInput) {
                    e.preventDefault();
                    swapFaces();
                    return;
                }
            }
        }
    });
}

// ── Init ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    cacheDom();
    setupEvents();
    loadData();
});
