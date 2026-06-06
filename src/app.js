/* ============================================================
   Cardlish Learn — App v2.0
   Flashcard learning app for elementary school students
   TV-optimized · Lesson management · Pre-generated TTS audio
   Vanilla JavaScript · No dependencies
   ============================================================ */

// ── Configuration ───────────────────────────────────────────
const CONFIG = {
  DATA_URL: '../public/data/cards.json',
  VOCAB_URL: '../public/data/cards_vocab.json',
  LESSONS_URL: '../public/data/lessons.json',
  VOCAB_AUDIO_MAP_URL: '../public/data/vocab_audio_map.json',
  CARDS_BASE_PATH: '../unified_db/',
  AUDIO_BASE_PATH: '../public/',
  STORAGE_KEY: 'cardlish_current_index',
  LESSONS_STORAGE_KEY: 'cardlish_lessons',
  CONTROLS: ['prev-card', 'play-audio', 'next-card'],
  POINTER_HIDE_DELAY: 3000,
  SWIPE_THRESHOLD: 50,
  ACTION_THROTTLE_MS: 300,
};

// ── Application State ───────────────────────────────────────
const state = {
  cards: [],
  vocab: {},
  currentIndex: 0,
  showingFront: true,
  activeControlIndex: 1, // play-audio by default
  audioPlaying: false,
  audioElement: null,
  navigationDirection: 'fade',
};

// ── Lesson State ────────────────────────────────────────────
const lessonState = {
  lessons: [],           // Merged: default (from file) + custom (from localStorage)
  activeLessonId: null,  // Currently selected lesson ID
};

// ── Vocab Audio Map (pre-generated MP3s) ────────────────────
let vocabAudioMap = null; // { words: { word: path }, sentences: { text: path } }
let sharedAudio = null;   // Single shared Audio element (TV only allows one)

// ── Throttle Lock ───────────────────────────────────────────
let actionLocked = false;

// ── Gallery State ───────────────────────────────────────────
const galleryState = {
  isOpen: false,
  searchQuery: '',
  activeColorFilters: new Set(), // empty = show all
  selectedCount: 'all',          // number or 'all'
  filteredCards: [],              // result of search + color filter
  studySet: [],                   // indices into state.cards for current session
  studySetActive: false,          // whether we're constraining to a study set
  selectedCardIndices: new Set(), // Set of selected indices in state.cards
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
  dom.sentencesContainer = document.getElementById('sentencesContainer');
  dom.frontImage = document.getElementById('frontImage');
  dom.backImage = document.getElementById('backImage');
  dom.cardLabel = document.getElementById('cardLabel');
  dom.cardSide = document.getElementById('cardSide');
  dom.cardInfo = document.getElementById('cardInfo');
  dom.prevCard = document.getElementById('prevCard');
  dom.playAudio = document.getElementById('playAudio');
  dom.nextCard = document.getElementById('nextCard');
  dom.loadingOverlay = document.getElementById('loadingOverlay');
  dom.mainContent = document.getElementById('mainContent');
  dom.vocabLeft = document.getElementById('vocabLeft');
  dom.vocabRight = document.getElementById('vocabRight');

  // Gallery DOM elements
  dom.galleryToggle = document.getElementById('galleryToggle');
  dom.galleryOverlay = document.getElementById('galleryOverlay');
  dom.galleryBack = document.getElementById('galleryBack');
  dom.searchInput = document.getElementById('searchInput');
  dom.searchClear = document.getElementById('searchClear');
  dom.colorFilters = document.getElementById('colorFilters');
  dom.cardCountSelector = document.getElementById('cardCountSelector');
  dom.customCountInput = document.getElementById('customCountInput');
  dom.gallerySummary = document.getElementById('gallerySummary');
  dom.filteredCount = document.getElementById('filteredCount');
  dom.selectedCardsList = document.getElementById('selectedCardsList');
  dom.startStudying = document.getElementById('startStudying');
  dom.galleryGrid = document.getElementById('galleryGrid');

  // Vocabulary Editor DOM elements
  dom.vocabEditOverlay = document.getElementById('vocabEditOverlay');
  dom.vocabEditClose = document.getElementById('vocabEditClose');
  dom.vocabEditCancel = document.getElementById('vocabEditCancel');
  dom.vocabEditSave = document.getElementById('vocabEditSave');
  dom.frontVocabList = document.getElementById('frontVocabList');
  dom.backVocabList = document.getElementById('backVocabList');
  dom.addFrontWord = document.getElementById('addFrontWord');
  dom.addBackWord = document.getElementById('addBackWord');
  dom.vocabEditTitle = document.getElementById('vocabEditTitle');
  dom.exportVocabJson = document.getElementById('exportVocabJson');

  // Home Screen DOM elements
  dom.homeScreen = document.getElementById('homeScreen');
  dom.studyScreen = document.getElementById('studyScreen');
  dom.lessonGrid = document.getElementById('lessonGrid');
  dom.backToHome = document.getElementById('backToHome');

  // Lesson action buttons
  dom.createLessonBtn = document.getElementById('createLessonBtn');
  dom.importLessonBtn = document.getElementById('importLessonBtn');
  dom.exportLessonBtn = document.getElementById('exportLessonBtn');
  dom.importLessonFile = document.getElementById('importLessonFile');

  // Create Lesson Modal
  dom.createLessonOverlay = document.getElementById('createLessonOverlay');
  dom.lessonNameInput = document.getElementById('lessonNameInput');
  dom.lessonCardsInput = document.getElementById('lessonCardsInput');
  dom.cancelCreateLesson = document.getElementById('cancelCreateLesson');
  dom.confirmCreateLesson = document.getElementById('confirmCreateLesson');
}

// ── Data Loader ─────────────────────────────────────────────
async function loadCards() {
  // Load both cards list and vocab list in parallel
  const [cardsResp, vocabResp] = await Promise.all([
    fetch(CONFIG.DATA_URL),
    fetch(CONFIG.VOCAB_URL).catch(e => {
      console.warn('Failed to load cards_vocab.json, fallback to empty:', e);
      return null;
    })
  ]);

  if (!cardsResp.ok) {
    throw new Error(`Không thể tải dữ liệu thẻ (HTTP ${cardsResp.status})`);
  }

  const data = await cardsResp.json();
  
  if (vocabResp && vocabResp.ok) {
    try {
      state.vocab = await vocabResp.json();
    } catch (e) {
      console.warn('Failed to parse cards_vocab.json:', e);
      state.vocab = {};
    }
  } else {
    state.vocab = {};
  }

  // Merge vocabulary overrides from localStorage
  try {
    const localEdits = localStorage.getItem('cardlish_vocab_edits');
    if (localEdits) {
      const parsedEdits = JSON.parse(localEdits);
      state.vocab = { ...state.vocab, ...parsedEdits };
    }
  } catch (err) {
    console.warn('Failed to load local vocab edits:', err);
  }

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
  dom.cardContainer.classList.remove('card-enter-next', 'card-enter-prev', 'card-enter-fade');
  // Force reflow to restart animation
  void dom.cardContainer.offsetWidth;
  
  const animClass = `card-enter-${state.navigationDirection || 'fade'}`;
  dom.cardContainer.classList.add(animClass);

  // Remove animation class after it finishes
  dom.cardContainer.addEventListener('animationend', () => {
    dom.cardContainer.classList.remove(animClass);
  }, { once: true });

  // Preload next card images
  preloadAdjacentCards();

  // Update audio button state
  updateAudioButton();

  // Save position
  savePosition();

  // Render vocabulary pills for the active card face
  renderVocab();
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
    dom.playAudio.textContent = '🔊';
    dom.playAudio.setAttribute('aria-label', 'Nghe âm thanh');
  } else {
    dom.playAudio.disabled = true;
    dom.playAudio.textContent = '🔇';
    dom.playAudio.setAttribute('aria-label', 'Chưa có âm thanh');
  }
}

// ── Throttle Utility (TV Performance) ───────────────────────
function throttledAction(fn) {
  if (actionLocked) return;
  actionLocked = true;
  fn();
  setTimeout(() => { actionLocked = false; }, CONFIG.ACTION_THROTTLE_MS);
}

function addPressedFeedback(btn) {
  if (!btn) return;
  btn.classList.add('btn-pressed');
  setTimeout(() => btn.classList.remove('btn-pressed'), 150);
}

// ── Card Actions ────────────────────────────────────────────
function flipCard() {
  state.showingFront = !state.showingFront;
  dom.cardContainer.classList.toggle('flipped');
  updateSideText();
  renderVocab();
  playAudioAuto();
}

function prevCard() {
  state.navigationDirection = 'prev';
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
  state.navigationDirection = 'next';
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
  playSharedAudio(audioPath, true);
}

function playAudioAuto() {
  const card = state.cards[state.currentIndex];
  if (!card.audio || card.audio.status !== 'downloaded' || !card.audio.local_path) {
    return;
  }

  // Stop current audio first
  stopAudio();

  const audioPath = CONFIG.AUDIO_BASE_PATH + card.audio.local_path;
  playSharedAudio(audioPath, true);
}

// ── Shared Audio Engine (TV: only 1 Audio element allowed) ──
function getSharedAudio() {
  if (!sharedAudio) {
    sharedAudio = new Audio();
  }
  return sharedAudio;
}

function playSharedAudio(src, isCardAudio) {
  try {
    const audio = getSharedAudio();
    audio.pause();
    audio.src = src;
    audio.currentTime = 0;

    if (isCardAudio) {
      state.audioPlaying = true;
      if (dom.playAudio) dom.playAudio.classList.add('audio-playing');
      audio.onended = () => stopAudio();
      audio.onerror = () => stopAudio();
    } else {
      audio.onended = null;
      audio.onerror = null;
    }

    audio.play().catch(err => {
      console.warn('Audio playback failed:', err);
      if (isCardAudio) stopAudio();
    });
  } catch (err) {
    console.warn('Audio error:', err);
    if (isCardAudio) stopAudio();
  }
}

function stopAudio() {
  if (sharedAudio) {
    sharedAudio.pause();
    sharedAudio.currentTime = 0;
  }
  state.audioPlaying = false;
  if (dom.playAudio) dom.playAudio.classList.remove('audio-playing');
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
  }
}

function executeActiveControl() {
  const action = CONFIG.CONTROLS[state.activeControlIndex];
  triggerAction(action);
}

function triggerAction(action) {
  // Wrap navigation in throttle to prevent TV UI freezing
  switch (action) {
    case 'prev-card':
      throttledAction(() => { addPressedFeedback(dom.prevCard); prevCard(); });
      break;
    case 'play-audio':
      throttledAction(() => { addPressedFeedback(dom.playAudio); playAudio(); });
      break;
    case 'flip-card':
      throttledAction(flipCard);
      break;
    case 'next-card':
      throttledAction(() => { addPressedFeedback(dom.nextCard); nextCard(); });
      break;
  }
}

// Helper to auto-select first N filtered cards
function autoSelectFiltered(count) {
  galleryState.selectedCardIndices.clear();
  const filtered = galleryState.filteredCards;
  const limit = count === 'all' ? filtered.length : count;
  for (let i = 0; i < Math.min(limit, filtered.length); i++) {
    const realIndex = state.cards.indexOf(filtered[i]);
    if (realIndex !== -1) {
      galleryState.selectedCardIndices.add(realIndex);
    }
  }
}

// Parse custom card selection input string (supporting spaces, commas, periods, slashes, semicolons, and dashes)
function parseCardNumbers(str) {
  const selectedNumbers = new Set();
  if (!str) return selectedNumbers;

  // Normalize range dashes (remove whitespace around them)
  let sanitized = str.replace(/\s*-\s*/g, '-');
  
  // Replace delimiters with spaces
  sanitized = sanitized.replace(/[\s,./;]+/g, ' ');
  
  // Split to tokens
  const tokens = sanitized.trim().split(/\s+/);
  
  for (const token of tokens) {
    if (!token) continue;
    
    if (token.includes('-')) {
      const parts = token.split('-');
      if (parts.length === 2) {
        const start = parseInt(parts[0], 10);
        const end = parseInt(parts[1], 10);
        if (!isNaN(start) && !isNaN(end)) {
          const min = Math.min(start, end);
          const max = Math.max(start, end);
          for (let i = min; i <= max; i++) {
            selectedNumbers.add(i);
          }
        }
      }
    } else {
      const num = parseInt(token, 10);
      if (!isNaN(num)) {
        selectedNumbers.add(num);
      }
    }
  }
  return selectedNumbers;
}

// Select cards based on a Set of card numbers
function selectCardsByNumbers(numberSet) {
  galleryState.selectedCardIndices.clear();
  state.cards.forEach((card, idx) => {
    const cardNum = parseInt(String(card.card_no || '').replace(/\D/g, ''), 10) || (idx + 1);
    if (numberSet.has(cardNum)) {
      galleryState.selectedCardIndices.add(idx);
    }
  });
}

// Get sorted array of selected card numbers (1-based)
function getSelectedCardNumbers() {
  const numbers = [];
  galleryState.selectedCardIndices.forEach((idx) => {
    const card = state.cards[idx];
    if (card) {
      const cardNum = parseInt(String(card.card_no || '').replace(/\D/g, ''), 10) || (idx + 1);
      numbers.push(cardNum);
    }
  });
  return numbers.sort((a, b) => a - b);
}

// Compress array of numbers into range expression string (e.g. 1, 3, 5-8)
function compressRanges(numbers) {
  if (numbers.length === 0) return '';
  const ranges = [];
  let start = numbers[0];
  let prev = numbers[0];
  
  for (let i = 1; i <= numbers.length; i++) {
    const current = numbers[i];
    if (current === prev + 1) {
      prev = current;
    } else {
      if (start === prev) {
        ranges.push(String(start));
      } else if (prev === start + 1) {
        ranges.push(String(start));
        ranges.push(String(prev));
      } else {
        ranges.push(`${start}-${prev}`);
      }
      if (current !== undefined) {
        start = current;
        prev = current;
      }
    }
  }
  return ranges.join(', ');
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

    const countVal = btn.dataset.count;
    galleryState.selectedCount = countVal === 'all' ? 'all' : parseInt(countVal, 10);

    autoSelectFiltered(galleryState.selectedCount);
    
    // Sync active state
    syncCountButtons();

    // Populate custom input with current selection ranges
    if (dom.customCountInput) {
      if (galleryState.selectedCardIndices.size === 0) {
        dom.customCountInput.value = '';
      } else {
        dom.customCountInput.value = compressRanges(getSelectedCardNumbers());
      }
    }

    buildGalleryGrid();
    updateGallerySummary();
  });

  // Custom count input change
  if (dom.customCountInput) {
    dom.customCountInput.addEventListener('input', () => {
      const valStr = dom.customCountInput.value.trim();
      if (!valStr) {
        galleryState.selectedCardIndices.clear();
        galleryState.selectedCount = 0;
        syncCountButtons();
        buildGalleryGrid();
        updateGallerySummary();
        return;
      }

      const numberSet = parseCardNumbers(valStr);
      selectCardsByNumbers(numberSet);
      galleryState.selectedCount = 'custom';
      
      syncCountButtons();
      buildGalleryGrid();
      updateGallerySummary();
    });
  }

  // Start studying button
  dom.startStudying.addEventListener('click', () => {
    applyStudySelection();
  });

  // Gallery card clicks (delegated)
  dom.galleryGrid.addEventListener('click', (e) => {
    const editBtn = e.target.closest('.vocab-edit-trigger');
    if (editBtn) {
      e.stopPropagation();
      const idx = parseInt(editBtn.dataset.index, 10);
      if (!isNaN(idx)) openVocabEditor(idx);
      return;
    }

    const card = e.target.closest('.gallery-card');
    if (!card) return;

    const idx = parseInt(card.dataset.index, 10);
    if (isNaN(idx)) return;

    // Toggle selection
    if (galleryState.selectedCardIndices.has(idx)) {
      galleryState.selectedCardIndices.delete(idx);
      card.classList.remove('selected');
    } else {
      galleryState.selectedCardIndices.add(idx);
      card.classList.add('selected');
    }

    // Set count to custom since selection changed manually
    if (galleryState.selectedCardIndices.size === 0) {
      galleryState.selectedCount = 0;
    } else {
      galleryState.selectedCount = 'custom';
    }
    syncCountButtons();

    if (dom.customCountInput) {
      dom.customCountInput.value = compressRanges(getSelectedCardNumbers());
    }

    updateGallerySummary();
  });

  setupVocabEditorListeners();
}

function setupKeyboardNavigation() {
  document.addEventListener('keydown', (e) => {
    // Ignore if typing in an input
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    // Handle Escape globally
    if (e.key === 'Escape') {
      e.preventDefault();
      if (galleryState.isOpen) {
        closeGallery();
      } else if (dom.createLessonOverlay && !dom.createLessonOverlay.hidden) {
        closeCreateLessonModal();
      } else if (!dom.studyScreen.hidden) {
        showHomeScreen();
      }
      return;
    }

    // Only handle study-mode keys when study screen is visible
    if (dom.studyScreen.hidden) return;

    switch (e.key) {
      case 'ArrowLeft':
        e.preventDefault();
        triggerAction('prev-card');
        break;

      case 'ArrowRight':
        e.preventDefault();
        triggerAction('next-card');
        break;

      case ' ':
        e.preventDefault(); // Prevent page scroll
        triggerAction('flip-card');
        break;

      case 'Enter':
        e.preventDefault();
        triggerAction('play-audio');
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

  // Initialize selected indices from current session studySet if active
  galleryState.selectedCardIndices.clear();
  if (galleryState.studySetActive && galleryState.studySet.length > 0) {
    galleryState.studySet.forEach(idx => galleryState.selectedCardIndices.add(idx));
    galleryState.selectedCount = 'custom';
    if (dom.customCountInput) {
      dom.customCountInput.value = compressRanges(getSelectedCardNumbers());
    }
  } else {
    // Select all cards by default
    galleryState.selectedCount = 'all';
    for (let i = 0; i < state.cards.length; i++) {
      galleryState.selectedCardIndices.add(i);
    }
    if (dom.customCountInput) {
      dom.customCountInput.value = compressRanges(getSelectedCardNumbers());
    }
  }

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
    const isSelected = galleryState.selectedCardIndices.has(realIndex);

    // Determine border color from the card's color
    const borderColor = colorHex;

    html += `<div class="gallery-card ${isSelected ? 'selected' : ''}" data-index="${realIndex}" style="border-color: ${borderColor}40;">
      <div class="check-overlay" aria-hidden="true">✓</div>
      <div class="gallery-card-img">
        <img src="${imgSrc}" alt="Thẻ ${cardNo}" loading="lazy" draggable="false">
        <div class="gallery-color-dot" style="background: ${colorHex};" title="${colorGroup}"></div>
      </div>
      <div class="gallery-card-footer">
        <span class="gallery-card-label">Thẻ ${cardNo}</span>
        <button class="vocab-edit-trigger focusable" data-index="${realIndex}" aria-label="Sửa từ vựng" title="Sửa từ vựng">✏️</button>
      </div>
    </div>`;
  });

  dom.galleryGrid.innerHTML = html;
}

// ── Update Gallery Summary ──────────────────────────────────
function updateGallerySummary() {
  const selectedCount = galleryState.selectedCardIndices.size;
  const totalCards = state.cards.length;
  dom.filteredCount.textContent = `Đã chọn ${selectedCount} / ${totalCards} thẻ`;

  if (dom.selectedCardsList) {
    const selectedNos = [];
    galleryState.selectedCardIndices.forEach((idx) => {
      const card = state.cards[idx];
      if (card) {
        selectedNos.push(card.card_no || String(idx + 1).padStart(3, '0'));
      }
    });
    
    selectedNos.sort((a, b) => {
      const numA = parseInt(a.replace(/\D/g, ''), 10) || 0;
      const numB = parseInt(b.replace(/\D/g, ''), 10) || 0;
      return numA - numB;
    });

    dom.selectedCardsList.textContent = selectedNos.length > 0 
      ? `Danh sách: ${selectedNos.join(', ')}` 
      : 'Danh sách: (trống)';
  }
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
  // Sort the selected indices so cards are studied in order
  galleryState.studySet = Array.from(galleryState.selectedCardIndices).sort((a, b) => a - b);

  if (galleryState.studySet.length > 0 && galleryState.studySet.length < state.cards.length) {
    galleryState.studySetActive = true;
    state.currentIndex = galleryState.studySet[0];
  } else {
    galleryState.studySetActive = false;
    galleryState.studySet = [];
  }

  renderCard();
  closeGallery();
}

// ── Go To Specific Card ─────────────────────────────────────
function goToCard(index) {
  if (index < 0 || index >= state.cards.length) return;

  state.navigationDirection = 'fade';
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

// ── Vocabulary Display & Pronunciation Speech ───────────────
function renderVocab() {
  if (!dom.vocabLeft || !dom.vocabRight) return;

  const card = state.cards[state.currentIndex];
  if (!card) {
    dom.vocabLeft.innerHTML = '';
    dom.vocabRight.innerHTML = '';
    if (dom.sentencesContainer) dom.sentencesContainer.style.display = 'none';
    return;
  }

  const cardVocab = state.vocab[card.pair_id];
  if (!cardVocab) {
    dom.vocabLeft.innerHTML = '';
    dom.vocabRight.innerHTML = '';
    if (dom.sentencesContainer) dom.sentencesContainer.style.display = 'none';
    return;
  }

  const words = state.showingFront ? (cardVocab.front || []) : (cardVocab.back || []);

  if (words.length === 0) {
    dom.vocabLeft.innerHTML = '';
    dom.vocabRight.innerHTML = '';
    if (dom.sentencesContainer) dom.sentencesContainer.style.display = 'none';
    return;
  }

  // Split words: left column gets the first half, right column gets the second half
  const mid = Math.ceil(words.length / 2);
  const leftWords = words.slice(0, mid);
  const rightWords = words.slice(mid);

  const makeButtonsHtml = (wordList) => {
    let html = '';
    wordList.forEach((item) => {
      const wordText = escapeHtml(item.word);
      const ipaText = item.ipa ? `<span class="vocab-word-ipa">${escapeHtml(item.ipa)}</span>` : '';
      html += `
        <button class="vocab-word-btn focusable" data-word="${wordText}" aria-label="Đọc từ ${wordText}">
          <span class="vocab-word-text">${wordText}</span>
          ${ipaText}
          <span class="vocab-word-speaker">🔊</span>
        </button>
      `;
    });
    return html;
  };

  dom.vocabLeft.innerHTML = makeButtonsHtml(leftWords);
  dom.vocabRight.innerHTML = makeButtonsHtml(rightWords);

  // Setup click listeners on all the newly rendered vocabulary buttons on both sides
  const setupBtnListeners = (container) => {
    container.querySelectorAll('.vocab-word-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation(); // Prevent card flipping
        const word = btn.dataset.word;
        speakWord(word);
      });
    });
  };

  setupBtnListeners(dom.vocabLeft);
  setupBtnListeners(dom.vocabRight);

  // Preload audio for all words and sentences on this card (TV: instant playback)
  preloadCardAudio();

  // Render sentences below the card
  if (dom.sentencesContainer) {
    const sentences = state.showingFront ? (cardVocab.front_sentences || []) : (cardVocab.back_sentences || []);
    if (sentences.length === 0) {
      dom.sentencesContainer.style.display = 'none';
    } else {
      dom.sentencesContainer.style.display = 'flex';
      let sentencesHtml = '';
      sentences.forEach((s) => {
        // Strip out the HTML tags (like <b>) for text speech synthesis
        const plainText = s.en.replace(/<\/?b>/g, '');
        
        sentencesHtml += `
          <div class="sentence-row">
            <span class="sentence-bullet">💡</span>
            <div class="sentence-text-group">
              <span class="sentence-en">${s.en}</span>
              <span class="sentence-vi">${escapeHtml(s.vi)}</span>
            </div>
            <button class="sentence-speaker-btn focusable" data-text="${escapeHtml(plainText)}" aria-label="Đọc câu ví dụ" title="Nghe đọc câu">🔊</button>
          </div>
        `;
      });
      dom.sentencesContainer.innerHTML = sentencesHtml;

      // Setup sentence speaker click listeners
      dom.sentencesContainer.querySelectorAll('.sentence-speaker-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation(); // Prevent card flipping
          const text = btn.dataset.text;
          speakSentence(text);
        });
      });
    }
  }
}

function getBestVoice() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return null;
  const voices = window.speechSynthesis.getVoices();
  
  const preferences = [
    'Google US English', 
    'Microsoft Aria Online',
    'Samantha',
    'Siri',
    'Microsoft Zira',
    'Google UK English Female',
    'en-US',
    'en-GB'
  ];

  for (const pref of preferences) {
    const voice = voices.find(v => v.lang.startsWith('en') && v.name.toLowerCase().includes(pref.toLowerCase()));
    if (voice) return voice;
  }

  return voices.find(v => v.lang.startsWith('en')) || null;
}

// ── TTS Audio Preload Cache (TV: warm browser cache via fetch) ─
const audioPreloadedSet = new Set(); // Track which URLs we've preloaded

function preloadAudioFile(src) {
  if (!src || audioPreloadedSet.has(src)) return;
  audioPreloadedSet.add(src);
  // Use fetch to warm the browser HTTP cache (no Audio elements needed)
  fetch(src).catch(() => {});
}

function preloadCardAudio() {
  if (!vocabAudioMap) return;
  const card = state.cards[state.currentIndex];
  if (!card) return;
  const cardVocab = state.vocab[card.pair_id];
  if (!cardVocab) return;

  // Preload vocab word audio for current side
  const words = state.showingFront ? (cardVocab.front || []) : (cardVocab.back || []);
  words.forEach(item => {
    if (item.word && vocabAudioMap.words) {
      const key = item.word.toLowerCase();
      if (vocabAudioMap.words[key]) {
        preloadAudioFile(CONFIG.AUDIO_BASE_PATH + vocabAudioMap.words[key]);
      }
    }
  });

  // Preload sentence audio for current side
  const sentences = state.showingFront
    ? (cardVocab.front_sentences || [])
    : (cardVocab.back_sentences || []);
  sentences.forEach(s => {
    if (s.en && vocabAudioMap.sentences) {
      const plainText = s.en.replace(/<\/?b>/g, '');
      if (vocabAudioMap.sentences[plainText]) {
        preloadAudioFile(CONFIG.AUDIO_BASE_PATH + vocabAudioMap.sentences[plainText]);
      }
    }
  });
}

// ── TTS Audio Playback (pre-generated MP3) ──────────────────
function playTTSAudio(src) {
  // Use the same shared Audio element as card audio (TV compatibility)
  stopAudio();
  playSharedAudio(src, false);
}

function speakSentence(text) {
  if (!text) return;

  // Strategy 1: Pre-generated MP3 (works on TV + everywhere)
  if (vocabAudioMap && vocabAudioMap.sentences && vocabAudioMap.sentences[text]) {
    const src = CONFIG.AUDIO_BASE_PATH + vocabAudioMap.sentences[text];
    playTTSAudio(src);
    return;
  }

  // Strategy 2: Fallback to speechSynthesis (desktop/mobile only)
  try {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
      }

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'en-US';
      utterance.volume = 1.0;
      utterance.rate = 0.80; // Slower, clearer rate for children
      utterance.pitch = 1.15; // Higher, more cheerful child-friendly pitch

      const voice = getBestVoice();
      if (voice) {
        utterance.voice = voice;
      }

      window.speechSynthesis.speak(utterance);
    }
  } catch (error) {
    console.warn('TTS speakSentence error:', error);
  }
}

function speakWord(word) {
  if (!word) return;

  // Strategy 1: Pre-generated MP3 (works on TV + everywhere)
  if (vocabAudioMap && vocabAudioMap.words && vocabAudioMap.words[word.toLowerCase()]) {
    const src = CONFIG.AUDIO_BASE_PATH + vocabAudioMap.words[word.toLowerCase()];
    playTTSAudio(src);
    return;
  }

  // Strategy 2: Fallback to speechSynthesis (desktop/mobile only)
  try {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
      }

      const utterance = new SpeechSynthesisUtterance(word);
      utterance.lang = 'en-US';
      utterance.volume = 1.0;
      utterance.rate = 0.78; // Slightly slower rate for clean phonics
      utterance.pitch = 1.15; // Higher, gentle child-friendly pitch

      const voice = getBestVoice();
      if (voice) {
        utterance.voice = voice;
      }

      window.speechSynthesis.speak(utterance);
    }
  } catch (err) {
    console.warn('Speech synthesis error:', err);
  }
}

// ── Vocabulary Editor Feature ────────────────────────────────
let activeEditingCardIndex = null;

function openVocabEditor(index) {
  const card = state.cards[index];
  if (!card) return;

  activeEditingCardIndex = index;
  const cardNo = card.card_no || `#${index + 1}`;
  dom.vocabEditTitle.textContent = `✏️ Sửa từ vựng - Thẻ ${cardNo}`;

  const cardVocab = state.vocab[card.pair_id] || { front: [], back: [] };
  
  // Render Front & Back lists
  renderEditorList(dom.frontVocabList, cardVocab.front || []);
  renderEditorList(dom.backVocabList, cardVocab.back || []);

  // Show overlay
  dom.vocabEditOverlay.removeAttribute('hidden');
}

function renderEditorList(container, words) {
  container.innerHTML = '';
  words.forEach(item => {
    addEditorRow(container, item.word, item.ipa);
  });
}

function addEditorRow(container, word = '', ipa = '') {
  const row = document.createElement('div');
  row.className = 'vocab-edit-row';
  
  row.innerHTML = `
    <input type="text" class="word-input focusable" placeholder="Từ vựng (ví dụ: apple)" value="${escapeHtml(word)}">
    <input type="text" class="ipa-input focusable" placeholder="Phiên âm (ví dụ: /æpl/)" value="${escapeHtml(ipa)}">
    <button class="vocab-delete-row-btn focusable" aria-label="Xóa dòng" title="Xóa dòng">🗑️</button>
  `;

  // Bind delete button
  row.querySelector('.vocab-delete-row-btn').addEventListener('click', () => {
    row.remove();
  });

  container.appendChild(row);
}

function closeVocabEditor() {
  dom.vocabEditOverlay.setAttribute('hidden', 'true');
  activeEditingCardIndex = null;
}

function saveVocabEdits() {
  if (activeEditingCardIndex === null) return;
  const card = state.cards[activeEditingCardIndex];
  if (!card) return;

  const getWordsFromList = (container) => {
    const words = [];
    container.querySelectorAll('.vocab-edit-row').forEach(row => {
      const wordInput = row.querySelector('.word-input');
      const ipaInput = row.querySelector('.ipa-input');
      const word = wordInput.value.trim();
      const ipa = ipaInput.value.trim();
      if (word) {
        words.push({ word, ipa });
      }
    });
    return words;
  };

  const frontWords = getWordsFromList(dom.frontVocabList);
  const backWords = getWordsFromList(dom.backVocabList);

  // Update in state
  state.vocab[card.pair_id] = {
    front: frontWords,
    back: backWords
  };

  // Save to localStorage
  try {
    localStorage.setItem('cardlish_vocab_edits', JSON.stringify(state.vocab));
  } catch (e) {
    console.warn('Failed to save vocab edits to localStorage:', e);
  }

  // If we're editing the current card, re-render the study screen vocabulary list
  if (activeEditingCardIndex === state.currentIndex) {
    renderVocab();
  }

  closeVocabEditor();
}

function exportVocabJson() {
  try {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(state.vocab, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", "cards_vocab.json");
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  } catch (err) {
    alert('Không thể xuất file JSON: ' + err.message);
  }
}

// Helper to setup event listeners for the editor
function setupVocabEditorListeners() {
  // Add row listeners
  dom.addFrontWord.addEventListener('click', () => {
    addEditorRow(dom.frontVocabList);
  });

  dom.addBackWord.addEventListener('click', () => {
    addEditorRow(dom.backVocabList);
  });

  // Cancel & Close listeners
  dom.vocabEditClose.addEventListener('click', closeVocabEditor);
  dom.vocabEditCancel.addEventListener('click', closeVocabEditor);
  dom.vocabEditOverlay.addEventListener('click', (e) => {
    if (e.target === dom.vocabEditOverlay) {
      closeVocabEditor();
    }
  });

  // Save listener
  dom.vocabEditSave.addEventListener('click', saveVocabEdits);

  // Export JSON listener
  dom.exportVocabJson.addEventListener('click', exportVocabJson);
}

// ============================================================
//  Lesson Management Module
// ============================================================

// ── Load Lessons ────────────────────────────────────────────
async function loadLessons() {
  let defaultLessons = [];
  let localLessons = [];

  // Load default lessons from static file
  try {
    const resp = await fetch(CONFIG.LESSONS_URL);
    if (resp.ok) {
      defaultLessons = await resp.json();
      // Mark default lessons
      defaultLessons.forEach(l => { l._source = 'default'; });
    }
  } catch (e) {
    console.warn('Failed to load default lessons:', e);
  }

  // Load custom lessons from localStorage
  try {
    const stored = localStorage.getItem(CONFIG.LESSONS_STORAGE_KEY);
    if (stored) {
      localLessons = JSON.parse(stored);
      localLessons.forEach(l => { l._source = 'local'; });
    }
  } catch (e) {
    console.warn('Failed to load local lessons:', e);
  }

  // Merge: local lessons override defaults with same ID
  const merged = new Map();
  defaultLessons.forEach(l => merged.set(l.id, l));
  localLessons.forEach(l => merged.set(l.id, l));
  
  lessonState.lessons = Array.from(merged.values());
  
  // Sort: custom lessons first (newest first), then defaults
  lessonState.lessons.sort((a, b) => {
    if (a._source !== b._source) {
      return a._source === 'local' ? -1 : 1;
    }
    return new Date(b.createdAt) - new Date(a.createdAt);
  });
}

// ── Save Lessons to localStorage ────────────────────────────
function saveLessonsLocal() {
  try {
    const localOnly = lessonState.lessons.filter(l => l._source === 'local');
    localStorage.setItem(CONFIG.LESSONS_STORAGE_KEY, JSON.stringify(localOnly));
  } catch (e) {
    console.warn('Failed to save lessons:', e);
  }
}

// ── Create Lesson ───────────────────────────────────────────
function createLesson(name, cardsStr) {
  if (!name || !name.trim()) return;

  const cardNumbers = parseCardNumbers(cardsStr);
  if (cardNumbers.size === 0) return;

  const id = 'lesson_' + Date.now().toString(36);
  const lesson = {
    id,
    name: name.trim(),
    cards: Array.from(cardNumbers).sort((a, b) => a - b),
    createdAt: new Date().toISOString(),
    _source: 'local',
  };

  lessonState.lessons.unshift(lesson);
  saveLessonsLocal();
  renderLessonGrid();
}

// ── Delete Lesson ───────────────────────────────────────────
function deleteLesson(id) {
  const lesson = lessonState.lessons.find(l => l.id === id);
  if (!lesson) return;

  const confirmMsg = `Xóa bài học "${lesson.name}"?`;
  if (!confirm(confirmMsg)) return;

  lessonState.lessons = lessonState.lessons.filter(l => l.id !== id);
  saveLessonsLocal();
  renderLessonGrid();
}

// ── Select Lesson → Start Studying ──────────────────────────
async function selectLesson(id) {
  const lesson = lessonState.lessons.find(l => l.id === id);
  if (!lesson) return;

  lessonState.activeLessonId = id;

  // Show loading overlay while preloading audio
  dom.loadingOverlay.style.display = 'flex';
  dom.loadingOverlay.classList.remove('hidden');

  // Build study set from lesson card numbers
  let studyIndices = [];
  if (lesson.cards === 'all') {
    galleryState.studySetActive = false;
    galleryState.studySet = [];
    studyIndices = state.cards.map((_, i) => i);
  } else {
    const cardNumbers = new Set(lesson.cards);
    const indices = [];
    state.cards.forEach((card, idx) => {
      const cardNum = parseInt(String(card.card_no || '').replace(/\D/g, ''), 10) || (idx + 1);
      if (cardNumbers.has(cardNum)) {
        indices.push(idx);
      }
    });

    if (indices.length > 0) {
      galleryState.studySet = indices;
      galleryState.studySetActive = true;
      state.currentIndex = indices[0];
      studyIndices = indices;
    } else {
      galleryState.studySetActive = false;
      galleryState.studySet = [];
      state.currentIndex = 0;
    }
  }

  // Preload ALL audio for this lesson's cards
  await preloadLessonAudio(studyIndices);

  // Done loading — show study screen
  renderCard();
  showStudyScreen();
  hideLoading();
}

// ── Preload All Audio for a Lesson ──────────────────────────
function preloadLessonAudio(cardIndices) {
  return new Promise((resolve) => {
    if (!vocabAudioMap) { resolve(); return; }

    const audioSources = [];

    cardIndices.forEach(idx => {
      const card = state.cards[idx];
      if (!card) return;

      // Preload card's main audio
      if (card.audio && card.audio.status === 'downloaded' && card.audio.local_path) {
        audioSources.push(CONFIG.AUDIO_BASE_PATH + card.audio.local_path);
      }

      // Preload vocab word audio (both sides)
      const cardVocab = state.vocab[card.pair_id];
      if (!cardVocab) return;

      ['front', 'back'].forEach(side => {
        (cardVocab[side] || []).forEach(item => {
          if (item.word && vocabAudioMap.words) {
            const key = item.word.toLowerCase();
            if (vocabAudioMap.words[key]) {
              audioSources.push(CONFIG.AUDIO_BASE_PATH + vocabAudioMap.words[key]);
            }
          }
        });
      });

      // Preload sentence audio (both sides)
      ['front_sentences', 'back_sentences'].forEach(side => {
        (cardVocab[side] || []).forEach(s => {
          if (s.en && vocabAudioMap.sentences) {
            const plainText = s.en.replace(/<\/?b>/g, '');
            if (vocabAudioMap.sentences[plainText]) {
              audioSources.push(CONFIG.AUDIO_BASE_PATH + vocabAudioMap.sentences[plainText]);
            }
          }
        });
      });
    });

    // Deduplicate
    const uniqueSources = [...new Set(audioSources)];

    if (uniqueSources.length === 0) { resolve(); return; }

    let loaded = 0;
    const total = uniqueSources.length;
    const timeout = setTimeout(() => {
      // Safety: resolve after 8 seconds max even if not all loaded
      console.warn(`Audio preload timeout: ${loaded}/${total} loaded`);
      resolve();
    }, 8000);

    uniqueSources.forEach(src => {
      if (audioPreloadedSet.has(src)) {
        loaded++;
        if (loaded >= total) { clearTimeout(timeout); resolve(); }
        return;
      }
      audioPreloadedSet.add(src);
      fetch(src)
        .then(() => {
          loaded++;
          if (loaded >= total) { clearTimeout(timeout); resolve(); }
        })
        .catch(() => {
          loaded++;
          if (loaded >= total) { clearTimeout(timeout); resolve(); }
        });
    });
  });
}

// ── Render Lesson Grid ──────────────────────────────────────
function renderLessonGrid() {
  if (!dom.lessonGrid) return;

  if (lessonState.lessons.length === 0) {
    dom.lessonGrid.innerHTML = `
      <div class="lesson-empty">
        <div class="lesson-empty-emoji">📭</div>
        <p>Chưa có bài học nào. Hãy tạo bài học mới!</p>
      </div>
    `;
    return;
  }

  let html = '';
  lessonState.lessons.forEach(lesson => {
    const isAll = lesson.cards === 'all';
    const cardCount = isAll ? state.cards.length : lesson.cards.length;
    const dateStr = lesson.createdAt 
      ? new Date(lesson.createdAt).toLocaleDateString('vi-VN')
      : '';
    const isLocal = lesson._source === 'local';
    const extraClass = isAll ? ' lesson-card--all' : '';

    html += `
      <div class="lesson-card${extraClass}" data-lesson-id="${lesson.id}">
        <div class="lesson-card-name">${escapeHtml(lesson.name)}</div>
        <div class="lesson-card-meta">
          <span>📇 ${cardCount} thẻ</span>
          ${dateStr ? `<span>📅 ${dateStr}</span>` : ''}
          ${isLocal ? '<span>✏️ Tự tạo</span>' : ''}
        </div>
        <div class="lesson-card-actions">
          <button class="lesson-card-study-btn focusable" data-lesson-id="${lesson.id}">
            🎓 Học bài này
          </button>
          ${isLocal ? `<button class="lesson-card-delete-btn focusable" data-lesson-id="${lesson.id}" aria-label="Xóa bài học">🗑️</button>` : ''}
        </div>
      </div>
    `;
  });

  dom.lessonGrid.innerHTML = html;

  // Setup click listeners
  dom.lessonGrid.querySelectorAll('.lesson-card-study-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      selectLesson(btn.dataset.lessonId);
    });
  });

  dom.lessonGrid.querySelectorAll('.lesson-card-delete-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      deleteLesson(btn.dataset.lessonId);
    });
  });

  // Clicking the card itself also starts studying
  dom.lessonGrid.querySelectorAll('.lesson-card').forEach(card => {
    card.addEventListener('click', () => {
      selectLesson(card.dataset.lessonId);
    });
  });
}

// ── Screen Switching ────────────────────────────────────────
function showHomeScreen() {
  stopAudio();
  dom.homeScreen.hidden = false;
  dom.studyScreen.hidden = true;
  lessonState.activeLessonId = null;
  renderLessonGrid();
}

function showStudyScreen() {
  dom.homeScreen.hidden = true;
  dom.studyScreen.hidden = false;
  setActiveControl(1); // Default to play-audio
}

// ── Create Lesson Modal ─────────────────────────────────────
function openCreateLessonModal() {
  dom.createLessonOverlay.hidden = false;
  dom.lessonNameInput.value = '';
  dom.lessonCardsInput.value = '';
  setTimeout(() => dom.lessonNameInput.focus(), 100);
}

function closeCreateLessonModal() {
  dom.createLessonOverlay.hidden = true;
}

function handleCreateLesson() {
  const name = dom.lessonNameInput.value.trim();
  const cardsStr = dom.lessonCardsInput.value.trim();

  if (!name) {
    dom.lessonNameInput.focus();
    return;
  }
  if (!cardsStr) {
    dom.lessonCardsInput.focus();
    return;
  }

  createLesson(name, cardsStr);
  closeCreateLessonModal();
}

// ── Export/Import Lessons ───────────────────────────────────
function exportLessonsJSON() {
  try {
    // Export all lessons (without internal _source field)
    const exportData = lessonState.lessons.map(l => {
      const { _source, ...rest } = l;
      return rest;
    });
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(exportData, null, 2));
    const anchor = document.createElement('a');
    anchor.setAttribute("href", dataStr);
    anchor.setAttribute("download", "lessons.json");
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } catch (err) {
    alert('Không thể xuất file: ' + err.message);
  }
}

function importLessonsJSON(file) {
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const imported = JSON.parse(e.target.result);
      if (!Array.isArray(imported)) {
        alert('File JSON không hợp lệ. Cần là một mảng bài học.');
        return;
      }

      // Mark imported lessons as local
      imported.forEach(l => {
        l._source = 'local';
        if (!l.id) l.id = 'lesson_' + Date.now().toString(36) + '_' + Math.random().toString(36).substr(2, 4);
      });

      // Merge with existing
      const merged = new Map();
      lessonState.lessons.forEach(l => merged.set(l.id, l));
      imported.forEach(l => merged.set(l.id, l));
      lessonState.lessons = Array.from(merged.values());

      saveLessonsLocal();
      renderLessonGrid();
      alert(`Đã nhập ${imported.length} bài học thành công!`);
    } catch (err) {
      alert('Lỗi đọc file JSON: ' + err.message);
    }
  };
  reader.readAsText(file);
}

// ── Load Vocab Audio Map ────────────────────────────────────
async function loadVocabAudioMap() {
  try {
    const resp = await fetch(CONFIG.VOCAB_AUDIO_MAP_URL);
    if (resp.ok) {
      vocabAudioMap = await resp.json();
      console.log(`Vocab audio map loaded: ${Object.keys(vocabAudioMap.words || {}).length} words, ${Object.keys(vocabAudioMap.sentences || {}).length} sentences`);
    }
  } catch (e) {
    console.warn('Failed to load vocab audio map (TTS will fall back to speechSynthesis):', e);
  }
}

// ── Setup Home Screen Listeners ─────────────────────────────
function setupHomeScreenListeners() {
  // Back to home button
  dom.backToHome.addEventListener('click', () => {
    showHomeScreen();
  });

  // Create lesson
  dom.createLessonBtn.addEventListener('click', () => {
    openCreateLessonModal();
  });

  // Create lesson modal
  dom.cancelCreateLesson.addEventListener('click', closeCreateLessonModal);
  dom.confirmCreateLesson.addEventListener('click', handleCreateLesson);
  dom.createLessonOverlay.addEventListener('click', (e) => {
    if (e.target === dom.createLessonOverlay) closeCreateLessonModal();
  });

  // Enter key in lesson cards input → create
  dom.lessonCardsInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleCreateLesson();
    }
  });

  // Export lessons
  dom.exportLessonBtn.addEventListener('click', exportLessonsJSON);

  // Import lessons
  dom.importLessonBtn.addEventListener('click', () => {
    dom.importLessonFile.click();
  });
  dom.importLessonFile.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      importLessonsJSON(e.target.files[0]);
      e.target.value = ''; // Reset for re-import
    }
  });
}

// ── Initialization ──────────────────────────────────────────
async function init() {
  cacheDom();

  try {
    // Load all data in parallel
    await Promise.all([
      loadCards(),
      loadLessons(),
      loadVocabAudioMap(),
    ]);

    // Setup all event listeners
    setupEventListeners();
    setupKeyboardNavigation();
    setupPointerIndicator();
    setupSwipeGestures();
    setupHomeScreenListeners();

    // Show home screen (lesson selection) as landing page
    showHomeScreen();
    hideLoading();
  } catch (error) {
    console.error('Cardlish Learn init error:', error);
    showError(error.message || 'Đã xảy ra lỗi khi khởi động ứng dụng.');
  }
}

document.addEventListener('DOMContentLoaded', init);
