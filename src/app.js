/* ============================================================
   Cardlish Learn — App v0.1
   Flashcard learning app for elementary school students
   Vanilla JavaScript · No dependencies
   ============================================================ */

// ── Configuration ───────────────────────────────────────────
const CONFIG = {
  DATA_URL: '../public/data/cards.json',
  CARDS_BASE_PATH: '../unified_db/',
  AUDIO_BASE_PATH: '../public/',
  STORAGE_KEY: 'cardlish_current_index',
  CONTROLS: ['prev-card', 'play-audio', 'flip-card', 'next-card'],
  POINTER_HIDE_DELAY: 3000,
  SWIPE_THRESHOLD: 50,
};

// ── Application State ───────────────────────────────────────
const state = {
  cards: [],
  currentIndex: 0,
  showingFront: true,
  activeControlIndex: 1, // play-audio by default
  audioPlaying: false,
  audioElement: null,
};

// ── Gallery State ───────────────────────────────────────────
const galleryState = {
  isOpen: false,
  searchQuery: '',
  activeColorFilters: new Set(), // empty = show all
  selectedCount: 'all',          // number or 'all'
  filteredCards: [],              // result of search + color filter
  studySet: [],                   // indices into state.cards for current session
  studySetActive: false,          // whether we're constraining to a study set
};

// ── Color Mapping ───────────────────────────────────────────
const COLOR_MAP = {
  blue:   { emoji: '🔵', label: 'Xanh' },
  orange: { emoji: '🟠', label: 'Cam' },
  pink:   { emoji: '🩷', label: 'Hồng' },
  cyan:   { emoji: '🩵', label: 'Xanh lơ' },
  green:  { emoji: '🟢', label: 'Xanh lá' },
  yellow: { emoji: '🟡', label: 'Vàng' },
  red:    { emoji: '🔴', label: 'Đỏ' },
  purple: { emoji: '🟣', label: 'Tím' },
  white:  { emoji: '⚪', label: 'Trắng' },
  gray:   { emoji: '⚫', label: 'Xám' },
};

// ── DOM References (cached once) ────────────────────────────
const dom = {};

function cacheDom() {
  dom.pointerIndicator = document.getElementById('pointerIndicator');
  dom.cardCounter = document.getElementById('cardCounter');
  dom.progressFill = document.getElementById('progressFill');
  dom.progressBar = document.getElementById('progressBarContainer');
  dom.cardContainer = document.getElementById('cardContainer');
  dom.cardFlipper = document.getElementById('cardFlipper');
  dom.frontImage = document.getElementById('frontImage');
  dom.backImage = document.getElementById('backImage');
  dom.cardLabel = document.getElementById('cardLabel');
  dom.cardSide = document.getElementById('cardSide');
  dom.cardInfo = document.getElementById('cardInfo');
  dom.prevCard = document.getElementById('prevCard');
  dom.playAudio = document.getElementById('playAudio');
  dom.flipCard = document.getElementById('flipCard');
  dom.nextCard = document.getElementById('nextCard');
  dom.actionsBar = document.getElementById('actionsBar');
  dom.statusBar = document.getElementById('statusBar');
  dom.activeLabel = document.getElementById('activeLabel');
  dom.loadingOverlay = document.getElementById('loadingOverlay');
  dom.mainContent = document.getElementById('mainContent');

  // Gallery DOM elements
  dom.galleryToggle = document.getElementById('galleryToggle');
  dom.galleryOverlay = document.getElementById('galleryOverlay');
  dom.galleryBack = document.getElementById('galleryBack');
  dom.searchInput = document.getElementById('searchInput');
  dom.searchClear = document.getElementById('searchClear');
  dom.colorFilters = document.getElementById('colorFilters');
  dom.cardCountSelector = document.getElementById('cardCountSelector');
  dom.gallerySummary = document.getElementById('gallerySummary');
  dom.filteredCount = document.getElementById('filteredCount');
  dom.startStudying = document.getElementById('startStudying');
  dom.galleryGrid = document.getElementById('galleryGrid');
}

// ── Data Loader ─────────────────────────────────────────────
async function loadCards() {
  const response = await fetch(CONFIG.DATA_URL);
  if (!response.ok) {
    throw new Error(`Không thể tải dữ liệu thẻ (HTTP ${response.status})`);
  }

  const data = await response.json();

  // Handle both array and object-with-cards formats
  let rawCards = Array.isArray(data) ? data : (data.cards || []);

  // Filter out problematic cards
  const filtered = rawCards.filter((card) => {
    // Skip cards flagged for review
    if (card.needs_review === true) return false;
    // Skip batch OCR failures (pair_id starts with 'batch')
    if (card.pair_id && typeof card.pair_id === 'string' && card.pair_id.startsWith('batch')) return false;
    return true;
  });

  // Sort numerically by card_no
  filtered.sort((a, b) => {
    const numA = parseInt(String(a.card_no).replace(/\D/g, ''), 10) || 0;
    const numB = parseInt(String(b.card_no).replace(/\D/g, ''), 10) || 0;
    return numA - numB;
  });

  state.cards = filtered;

  if (state.cards.length === 0) {
    throw new Error('Không tìm thấy thẻ học nào. Vui lòng kiểm tra dữ liệu.');
  }

  // Restore saved position
  const saved = localStorage.getItem(CONFIG.STORAGE_KEY);
  if (saved !== null) {
    const idx = parseInt(saved, 10);
    if (!isNaN(idx) && idx >= 0 && idx < state.cards.length) {
      state.currentIndex = idx;
    }
  }
}

// ── Card Renderer ───────────────────────────────────────────
function renderCard() {
  const card = state.cards[state.currentIndex];
  if (!card) return;

  // Reset to front side
  state.showingFront = true;
  dom.cardContainer.classList.remove('flipped');

  // Set images
  const frontSrc = CONFIG.CARDS_BASE_PATH + card.front_image;
  const backSrc = CONFIG.CARDS_BASE_PATH + (card.back_image || card.front_image);
  dom.frontImage.src = frontSrc;
  dom.backImage.src = backSrc;
  dom.frontImage.alt = `Mặt trước - ${card.card_no || ''}`;
  dom.backImage.alt = `Mặt sau - ${card.card_no || ''}`;

  // Update counter — show study set position if active
  let current, total;
  if (galleryState.studySetActive && galleryState.studySet.length > 0) {
    const posInStudy = galleryState.studySet.indexOf(state.currentIndex);
    current = posInStudy >= 0 ? posInStudy + 1 : 1;
    total = galleryState.studySet.length;
  } else {
    current = state.currentIndex + 1;
    total = state.cards.length;
  }
  if (dom.cardCounter) dom.cardCounter.textContent = `Thẻ ${current} / ${total}`;

  // Update progress bar
  const pct = (current / total) * 100;
  dom.progressFill.style.width = `${pct}%`;
  dom.progressBar.setAttribute('aria-valuenow', Math.round(pct));

  // Update card info
  const label = card.card_no || `#${current}`;
  const extraLabel = card.label ? ` – ${card.label}` : '';
  dom.cardLabel.textContent = `Thẻ ${label}${extraLabel}`;
  updateSideText();

  // Entrance animation
  dom.cardContainer.classList.remove('card-enter');
  // Force reflow to restart animation
  void dom.cardContainer.offsetWidth;
  dom.cardContainer.classList.add('card-enter');

  // Remove animation class after it finishes
  dom.cardContainer.addEventListener('animationend', () => {
    dom.cardContainer.classList.remove('card-enter');
  }, { once: true });

  // Preload next card images
  preloadAdjacentCards();

  // Update audio button state
  updateAudioButton();

  // Save position
  savePosition();
}

function updateSideText() {
  dom.cardSide.textContent = state.showingFront ? '· Mặt trước' : '· Mặt sau';
}

function preloadAdjacentCards() {
  const preloadIndex = (state.currentIndex + 1) % state.cards.length;
  const nextCard = state.cards[preloadIndex];
  if (nextCard) {
    const imgFront = new Image();
    imgFront.src = CONFIG.CARDS_BASE_PATH + nextCard.front_image;
    if (nextCard.back_image) {
      const imgBack = new Image();
      imgBack.src = CONFIG.CARDS_BASE_PATH + nextCard.back_image;
    }
  }
}

function updateAudioButton() {
  const card = state.cards[state.currentIndex];
  const hasAudio = card.audio && card.audio.status === 'downloaded' && card.audio.local_path;

  if (hasAudio) {
    dom.playAudio.disabled = false;
    dom.playAudio.querySelector('.btn-text').textContent = 'Nghe âm';
    dom.playAudio.querySelector('.btn-icon').textContent = '🔊';
    dom.playAudio.setAttribute('aria-label', 'Nghe âm thanh');
  } else {
    dom.playAudio.disabled = true;
    dom.playAudio.querySelector('.btn-text').textContent = 'Chưa có âm';
    dom.playAudio.querySelector('.btn-icon').textContent = '🔇';
    dom.playAudio.setAttribute('aria-label', 'Chưa có âm thanh');
  }
}

// ── Card Actions ────────────────────────────────────────────
function flipCard() {
  state.showingFront = !state.showingFront;
  dom.cardContainer.classList.toggle('flipped');
  updateSideText();
}

function prevCard() {
  stopAudio();
  if (galleryState.studySetActive && galleryState.studySet.length > 0) {
    const pos = galleryState.studySet.indexOf(state.currentIndex);
    const prevPos = (pos - 1 + galleryState.studySet.length) % galleryState.studySet.length;
    state.currentIndex = galleryState.studySet[prevPos];
  } else {
    state.currentIndex = (state.currentIndex - 1 + state.cards.length) % state.cards.length;
  }
  renderCard();
}

function nextCard() {
  stopAudio();
  if (galleryState.studySetActive && galleryState.studySet.length > 0) {
    const pos = galleryState.studySet.indexOf(state.currentIndex);
    const nextPos = (pos + 1) % galleryState.studySet.length;
    state.currentIndex = galleryState.studySet[nextPos];
  } else {
    state.currentIndex = (state.currentIndex + 1) % state.cards.length;
  }
  renderCard();
}

function playAudio() {
  const card = state.cards[state.currentIndex];
  if (!card.audio || card.audio.status !== 'downloaded' || !card.audio.local_path) {
    return;
  }

  // If already playing, stop it
  if (state.audioPlaying) {
    stopAudio();
    return;
  }

  const audioPath = CONFIG.AUDIO_BASE_PATH + card.audio.local_path;

  try {
    if (!state.audioElement) {
      state.audioElement = new Audio();
    }

    state.audioElement.src = audioPath;
    state.audioElement.currentTime = 0;
    state.audioPlaying = true;
    dom.playAudio.classList.add('audio-playing');

    state.audioElement.play().catch((err) => {
      console.warn('Audio playback failed:', err);
      stopAudio();
    });

    state.audioElement.onended = () => {
      stopAudio();
    };

    state.audioElement.onerror = () => {
      console.warn('Audio file error');
      stopAudio();
    };
  } catch (err) {
    console.warn('Audio error:', err);
    stopAudio();
  }
}

function stopAudio() {
  if (state.audioElement) {
    state.audioElement.pause();
    state.audioElement.currentTime = 0;
  }
  state.audioPlaying = false;
  dom.playAudio.classList.remove('audio-playing');
}

// ── Persistence ─────────────────────────────────────────────
function savePosition() {
  try {
    localStorage.setItem(CONFIG.STORAGE_KEY, String(state.currentIndex));
  } catch (e) {
    // localStorage may be unavailable; silently ignore
  }
}

// ── Focus / Navigation Manager ──────────────────────────────
function getControlButtons() {
  return CONFIG.CONTROLS.map((action) =>
    document.querySelector(`[data-action="${action}"]`)
  );
}

function setActiveControl(index) {
  const buttons = getControlButtons();
  const total = buttons.length;

  // Clamp index
  index = ((index % total) + total) % total;
  state.activeControlIndex = index;

  // Remove active from all
  buttons.forEach((btn) => {
    if (btn) btn.removeAttribute('data-active');
  });

  const target = buttons[index];
  if (target) {
    target.setAttribute('data-active', 'true');
    target.focus({ preventScroll: true });

    // Update status bar
    const label = target.querySelector('.btn-icon').textContent + ' ' +
                  target.querySelector('.btn-text').textContent;
    if (dom.activeLabel) dom.activeLabel.textContent = label;
  }
}

function executeActiveControl() {
  const action = CONFIG.CONTROLS[state.activeControlIndex];
  triggerAction(action);
}

function triggerAction(action) {
  switch (action) {
    case 'prev-card':
      prevCard();
      break;
    case 'play-audio':
      playAudio();
      break;
    case 'flip-card':
      flipCard();
      break;
    case 'next-card':
      nextCard();
      break;
  }
}

// ── Event Listeners ─────────────────────────────────────────
function setupEventListeners() {
  // Button clicks
  const buttons = getControlButtons();
  buttons.forEach((btn, idx) => {
    if (!btn) return;

    btn.addEventListener('click', (e) => {
      e.preventDefault();
      setActiveControl(idx);
      triggerAction(btn.dataset.action);
    });
  });

  // Card click = flip
  dom.cardContainer.addEventListener('click', (e) => {
    e.preventDefault();
    flipCard();
  });

  // ── Gallery Event Listeners ──────────────────────────────
  // Open gallery
  dom.galleryToggle.addEventListener('click', () => {
    openGallery();
  });

  // Close gallery
  dom.galleryBack.addEventListener('click', () => {
    closeGallery();
  });

  // Search input — live filter
  dom.searchInput.addEventListener('input', () => {
    galleryState.searchQuery = dom.searchInput.value;
    dom.searchClear.hidden = !galleryState.searchQuery;
    filterGalleryCards();
  });

  // Search clear button
  dom.searchClear.addEventListener('click', () => {
    dom.searchInput.value = '';
    galleryState.searchQuery = '';
    dom.searchClear.hidden = true;
    dom.searchInput.focus();
    filterGalleryCards();
  });

  // Color filter chip clicks (delegated)
  dom.colorFilters.addEventListener('click', (e) => {
    const chip = e.target.closest('.color-chip');
    if (!chip) return;

    const colorGroup = chip.dataset.color;

    if (colorGroup === 'all') {
      // "Tất cả" chip — clear all filters
      galleryState.activeColorFilters.clear();
      dom.colorFilters.querySelectorAll('.color-chip').forEach((c) => {
        c.classList.toggle('active', c.dataset.color === 'all');
      });
    } else {
      // Toggle specific color
      const allChip = dom.colorFilters.querySelector('[data-color="all"]');
      if (galleryState.activeColorFilters.has(colorGroup)) {
        galleryState.activeColorFilters.delete(colorGroup);
        chip.classList.remove('active');
      } else {
        galleryState.activeColorFilters.add(colorGroup);
        chip.classList.add('active');
      }
      // Deactivate "all" chip if specific colors are selected
      if (allChip) {
        allChip.classList.toggle('active', galleryState.activeColorFilters.size === 0);
      }
    }
    filterGalleryCards();
  });

  // Count buttons (delegated)
  dom.cardCountSelector.addEventListener('click', (e) => {
    const btn = e.target.closest('.count-btn');
    if (!btn) return;

    const count = btn.dataset.count;
    galleryState.selectedCount = count === 'all' ? 'all' : parseInt(count, 10);

    // Update active state
    dom.cardCountSelector.querySelectorAll('.count-btn').forEach((b) => {
      b.classList.remove('active');
    });
    btn.classList.add('active');

    updateGallerySummary();
  });

  // Start studying button
  dom.startStudying.addEventListener('click', () => {
    applyStudySelection();
  });

  // Gallery card clicks (delegated)
  dom.galleryGrid.addEventListener('click', (e) => {
    const card = e.target.closest('.gallery-card');
    if (!card) return;

    const idx = parseInt(card.dataset.index, 10);
    if (isNaN(idx)) return;

    goToCard(idx);
  });
}

function setupKeyboardNavigation() {
  document.addEventListener('keydown', (e) => {
    // Ignore if typing in an input
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    switch (e.key) {
      case 'ArrowLeft':
        e.preventDefault();
        if (state.activeControlIndex > 0) {
          setActiveControl(state.activeControlIndex - 1);
        } else {
          prevCard();
        }
        break;

      case 'ArrowRight':
        e.preventDefault();
        if (state.activeControlIndex < CONFIG.CONTROLS.length - 1) {
          setActiveControl(state.activeControlIndex + 1);
        } else {
          nextCard();
        }
        break;

      case 'ArrowUp':
        e.preventDefault();
        flipCard();
        break;

      case 'ArrowDown':
        e.preventDefault();
        // Focus on buttons area – set to current active
        setActiveControl(state.activeControlIndex);
        break;

      case 'Enter':
        e.preventDefault();
        executeActiveControl();
        break;

      case ' ':
        e.preventDefault(); // Prevent page scroll
        executeActiveControl();
        break;

      case 'Escape':
        e.preventDefault();
        if (galleryState.isOpen) {
          closeGallery();
        } else {
          setActiveControl(1); // Reset to play-audio
        }
        break;

      default:
        break;
    }
  });
}

// ── Swipe Gestures ──────────────────────────────────────────
function setupSwipeGestures() {
  let touchStartX = 0;
  let touchStartY = 0;
  let touchStartTime = 0;
  let isSwiping = false;

  dom.cardContainer.addEventListener('touchstart', (e) => {
    const touch = e.touches[0];
    touchStartX = touch.clientX;
    touchStartY = touch.clientY;
    touchStartTime = Date.now();
    isSwiping = true;
  }, { passive: true });

  dom.cardContainer.addEventListener('touchmove', (e) => {
    // Allow default scrolling if mostly vertical
  }, { passive: true });

  dom.cardContainer.addEventListener('touchend', (e) => {
    if (!isSwiping) return;
    isSwiping = false;

    const touch = e.changedTouches[0];
    const deltaX = touch.clientX - touchStartX;
    const deltaY = touch.clientY - touchStartY;
    const elapsed = Date.now() - touchStartTime;

    // Must be a quick swipe (< 500ms) and mostly horizontal
    if (elapsed > 500) return;
    if (Math.abs(deltaX) < CONFIG.SWIPE_THRESHOLD) return;
    if (Math.abs(deltaY) > Math.abs(deltaX)) return;

    if (deltaX < -CONFIG.SWIPE_THRESHOLD) {
      // Swipe left → next card
      nextCard();
    } else if (deltaX > CONFIG.SWIPE_THRESHOLD) {
      // Swipe right → prev card
      prevCard();
    }
  }, { passive: true });
}

// ── Pointer Indicator ───────────────────────────────────────
function setupPointerIndicator() {
  // Only on devices with hover capability (desktop/TV)
  const hasHover = window.matchMedia('(hover: hover)').matches;
  if (!hasHover) return;

  const indicator = dom.pointerIndicator;
  let hideTimer = null;

  function showIndicator() {
    indicator.classList.add('visible');
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      indicator.classList.remove('visible');
    }, CONFIG.POINTER_HIDE_DELAY);
  }

  document.addEventListener('pointermove', (e) => {
    // Only for mouse pointers
    if (e.pointerType !== 'mouse') return;

    indicator.style.left = `${e.clientX}px`;
    indicator.style.top = `${e.clientY}px`;
    showIndicator();
  });

  document.addEventListener('pointerleave', () => {
    indicator.classList.remove('visible');
    clearTimeout(hideTimer);
  });

  // Hide during interaction
  document.addEventListener('pointerdown', () => {
    indicator.classList.remove('visible');
  });
}

// ── Loading / Error UI ──────────────────────────────────────
function hideLoading() {
  dom.loadingOverlay.classList.add('hidden');
  // Remove from DOM after transition
  setTimeout(() => {
    dom.loadingOverlay.style.display = 'none';
  }, 400);
}

function showError(message) {
  // Hide loading overlay
  dom.loadingOverlay.classList.add('hidden');

  // Show error in main content
  dom.mainContent.innerHTML = `
    <div class="error-message">
      <div class="error-emoji">😕</div>
      <p class="error-text">${escapeHtml(message)}</p>
    </div>
  `;

  // Disable all action buttons
  const buttons = getControlButtons();
  buttons.forEach((btn) => {
    if (btn) btn.disabled = true;
  });
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ============================================================
//  Gallery / Library Module
// ============================================================

// ── Open Gallery ────────────────────────────────────────────
function openGallery() {
  galleryState.isOpen = true;
  dom.galleryOverlay.hidden = false;
  dom.galleryOverlay.classList.remove('closing');

  // Reset search
  dom.searchInput.value = '';
  galleryState.searchQuery = '';
  dom.searchClear.hidden = true;

  // Build color filter chips (once, or rebuild if needed)
  buildColorFilterChips();

  // Reset count button to current selection
  syncCountButtons();

  // Filter and render
  filterGalleryCards();

  // Focus search input for keyboard accessibility
  setTimeout(() => dom.searchInput.focus(), 100);
}

// ── Close Gallery ───────────────────────────────────────────
function closeGallery() {
  galleryState.isOpen = false;
  dom.galleryOverlay.classList.add('closing');

  // Wait for slide-out animation to finish
  dom.galleryOverlay.addEventListener('animationend', function handler() {
    dom.galleryOverlay.removeEventListener('animationend', handler);
    dom.galleryOverlay.hidden = true;
    dom.galleryOverlay.classList.remove('closing');
  });
}

// ── Build Color Filter Chips ────────────────────────────────
function buildColorFilterChips() {
  // Count cards per color group
  const colorCounts = {};
  state.cards.forEach((card) => {
    const group = card.color && card.color.group ? card.color.group : 'unknown';
    colorCounts[group] = (colorCounts[group] || 0) + 1;
  });

  let html = '';

  // "All" chip
  const allActive = galleryState.activeColorFilters.size === 0 ? 'active' : '';
  html += `<button class="color-chip ${allActive}" data-color="all">
    <span class="chip-emoji">🎨</span> Tất cả
    <span class="chip-count">(${state.cards.length})</span>
  </button>`;

  // Color-specific chips — only show colors that exist in the data
  const orderedColors = Object.keys(COLOR_MAP);
  orderedColors.forEach((colorKey) => {
    const count = colorCounts[colorKey];
    if (!count) return; // skip colors with 0 cards

    const info = COLOR_MAP[colorKey];
    const active = galleryState.activeColorFilters.has(colorKey) ? 'active' : '';
    html += `<button class="color-chip ${active}" data-color="${colorKey}">
      <span class="chip-emoji">${info.emoji}</span> ${info.label}
      <span class="chip-count">(${count})</span>
    </button>`;
  });

  // Handle unknown/misc colors
  const knownColors = new Set(orderedColors);
  let miscCount = 0;
  Object.keys(colorCounts).forEach((key) => {
    if (!knownColors.has(key)) miscCount += colorCounts[key];
  });
  if (miscCount > 0) {
    const active = galleryState.activeColorFilters.has('misc') ? 'active' : '';
    html += `<button class="color-chip ${active}" data-color="misc">
      <span class="chip-emoji">🔘</span> Khác
      <span class="chip-count">(${miscCount})</span>
    </button>`;
  }

  dom.colorFilters.innerHTML = html;
}

// ── Filter Gallery Cards ────────────────────────────────────
function filterGalleryCards() {
  const query = galleryState.searchQuery.trim().toLowerCase();
  const activeColors = galleryState.activeColorFilters;
  const knownColors = new Set(Object.keys(COLOR_MAP));

  galleryState.filteredCards = state.cards.filter((card, idx) => {
    // Color filter
    if (activeColors.size > 0) {
      const cardColor = card.color && card.color.group ? card.color.group : 'unknown';
      let matchesColor = activeColors.has(cardColor);
      // "misc" matches any unknown color
      if (!matchesColor && activeColors.has('misc') && !knownColors.has(cardColor)) {
        matchesColor = true;
      }
      if (!matchesColor) return false;
    }

    // Search filter
    if (query) {
      const cardNo = String(card.card_no || '').toLowerCase();
      const pairId = String(card.pair_id || '').toLowerCase();
      const label = String(card.label || '').toLowerCase();
      const qrUrl = String(card.qr_url || '').toLowerCase();
      const searchable = `${cardNo} ${pairId} ${label} ${qrUrl}`;
      if (!searchable.includes(query)) return false;
    }

    return true;
  });

  buildGalleryGrid();
  updateGallerySummary();
}

// ── Build Gallery Grid ──────────────────────────────────────
function buildGalleryGrid() {
  const cards = galleryState.filteredCards;

  if (cards.length === 0) {
    dom.galleryGrid.innerHTML = `
      <div class="gallery-empty">
        <div class="empty-emoji">🔍</div>
        <p class="empty-text">Không tìm thấy thẻ nào</p>
      </div>`;
    return;
  }

  let html = '';
  cards.forEach((card) => {
    const realIndex = state.cards.indexOf(card);
    const imgSrc = CONFIG.CARDS_BASE_PATH + card.front_image;
    const cardNo = card.card_no || `#${realIndex + 1}`;
    const colorHex = card.color && card.color.hex ? card.color.hex : '#cccccc';
    const colorGroup = card.color && card.color.group ? card.color.group : '';

    // Determine border color from the card's color
    const borderColor = colorHex;

    html += `<div class="gallery-card" data-index="${realIndex}" style="border-color: ${borderColor}40;">
      <div class="check-overlay" aria-hidden="true">✓</div>
      <div class="gallery-card-img">
        <img src="${imgSrc}" alt="Thẻ ${cardNo}" loading="lazy" draggable="false">
        <div class="gallery-color-dot" style="background: ${colorHex};" title="${colorGroup}"></div>
      </div>
      <div class="gallery-card-label">${cardNo}</div>
    </div>`;
  });

  dom.galleryGrid.innerHTML = html;
}

// ── Update Gallery Summary ──────────────────────────────────
function updateGallerySummary() {
  const totalFiltered = galleryState.filteredCards.length;
  const count = galleryState.selectedCount;
  let studyCount;

  if (count === 'all' || count >= totalFiltered) {
    studyCount = totalFiltered;
  } else {
    studyCount = Math.min(count, totalFiltered);
  }

  dom.filteredCount.textContent = `Đã chọn ${studyCount} / ${totalFiltered} thẻ`;
}

// ── Sync Count Buttons ──────────────────────────────────────
function syncCountButtons() {
  const btns = dom.cardCountSelector.querySelectorAll('.count-btn');
  btns.forEach((btn) => {
    const val = btn.dataset.count;
    const matches = (galleryState.selectedCount === 'all' && val === 'all') ||
                    (String(galleryState.selectedCount) === val);
    btn.classList.toggle('active', matches);
  });
}

// ── Apply Study Selection ───────────────────────────────────
function applyStudySelection() {
  const filtered = galleryState.filteredCards;
  const count = galleryState.selectedCount;

  let selectedCards;
  if (count === 'all' || count >= filtered.length) {
    selectedCards = filtered;
  } else {
    selectedCards = filtered.slice(0, count);
  }

  // Build study set as array of indices into state.cards
  galleryState.studySet = selectedCards.map((card) => state.cards.indexOf(card));

  if (galleryState.studySet.length > 0 && galleryState.studySet.length < state.cards.length) {
    galleryState.studySetActive = true;
    // Start at the first card of the study set
    state.currentIndex = galleryState.studySet[0];
  } else {
    // Studying all cards — no constraint
    galleryState.studySetActive = false;
    galleryState.studySet = [];
  }

  renderCard();
  closeGallery();
}

// ── Go To Specific Card ─────────────────────────────────────
function goToCard(index) {
  if (index < 0 || index >= state.cards.length) return;

  stopAudio();

  // If going to a specific card via gallery click, disable study set constraint
  // so user can freely navigate from that card
  galleryState.studySetActive = false;
  galleryState.studySet = [];
  // Reset count button to "all"
  galleryState.selectedCount = 'all';

  state.currentIndex = index;
  renderCard();
  closeGallery();
}

// ── Initialization ──────────────────────────────────────────
async function init() {
  cacheDom();

  try {
    await loadCards();
    setupEventListeners();
    setupKeyboardNavigation();
    setupPointerIndicator();
    setupSwipeGestures();
    renderCard();
    setActiveControl(1); // Default to play-audio
    hideLoading();
  } catch (error) {
    console.error('Cardlish Learn init error:', error);
    showError(error.message || 'Đã xảy ra lỗi khi khởi động ứng dụng.');
  }
}

document.addEventListener('DOMContentLoaded', init);
