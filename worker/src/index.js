// ═══════════════════════════════════════════════════════════════════════════
// Cardlish Learn — Cloudflare Worker API
// ═══════════════════════════════════════════════════════════════════════════
//
// KV Keys:
//   data:lessons    → JSON array of lesson objects
//   data:cards      → JSON array of card objects
//   data:vocab      → JSON object keyed by pair_id
//   data:audio_map  → JSON object { words: {}, sentences: {} }
//   meta:version    → JSON { hash, updatedAt, updatedBy }
//   meta:device_keys→ JSON { "dk_xxx": { name, createdAt, lastUsed }, ... }
//
// ═══════════════════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════

/**
 * Build a JSON Response with CORS headers attached.
 * @param {any} body - Object to serialize
 * @param {number} status - HTTP status code
 * @param {Record<string,string>} corsHeaders - Pre-built CORS headers
 */
function jsonResponse(body, status, corsHeaders) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders },
  });
}

/**
 * Derive CORS headers from the incoming request's Origin.
 * Only reflects the origin if it appears in the allow-list.
 */
function buildCorsHeaders(request, env) {
  const origin = request.headers.get("Origin") || "";
  const allowed = (env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim());
  const headers = {
    "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400",
  };
  if (allowed.includes(origin)) {
    headers["Access-Control-Allow-Origin"] = origin;
  }
  return headers;
}

/**
 * Safely read and parse JSON from request body.
 * Returns { data, error }.
 */
async function safeParseJSON(request) {
  try {
    const text = await request.text();
    if (!text || text.trim() === "") {
      return { data: null, error: "Request body is required" };
    }
    const data = JSON.parse(text);
    return { data, error: null };
  } catch (e) {
    return { data: null, error: `Invalid JSON body: ${e.message}` };
  }
}

/**
 * Check that Content-Type is application/json (for write endpoints).
 * Returns an error string or null.
 */
function checkContentType(request) {
  const ct = request.headers.get("Content-Type") || "";
  if (!ct.includes("application/json")) {
    return "Content-Type must be application/json";
  }
  return null;
}

/**
 * Safely read a KV key and parse JSON. Returns the default value on miss.
 */
async function kvGet(kv, key, defaultValue) {
  try {
    const raw = await kv.get(key);
    if (raw === null || raw === undefined) return defaultValue;
    return JSON.parse(raw);
  } catch (e) {
    throw new Error(`KV read failed for key "${key}": ${e.message}`);
  }
}

/**
 * Safely write a JSON value to KV.
 */
async function kvPut(kv, key, value) {
  try {
    await kv.put(key, JSON.stringify(value));
  } catch (e) {
    throw new Error(`KV write failed for key "${key}": ${e.message}`);
  }
}

/**
 * Parse the URL path into segments, e.g. "/api/lessons/abc" → ["api","lessons","abc"]
 */
function pathSegments(url) {
  return new URL(url).pathname
    .split("/")
    .filter((s) => s.length > 0);
}

/**
 * Generate a short hash for version tracking.
 * Uses crypto.subtle for a SHA-256 of timestamp+random, returns first 8 hex chars.
 */
async function generateHash() {
  const input = `${Date.now()}-${crypto.randomUUID()}`;
  const encoded = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  const arr = Array.from(new Uint8Array(digest));
  return arr.map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 8);
}

/**
 * Bump the version metadata after a write operation.
 * Designed to be called via ctx.waitUntil() so it doesn't block the response.
 */
async function bumpVersion(kv, deviceName) {
  const hash = await generateHash();
  const version = {
    hash,
    updatedAt: new Date().toISOString(),
    updatedBy: deviceName || "unknown",
  };
  await kvPut(kv, "meta:version", version);
}

/**
 * Validate that `cards` field in a lesson is either the string "all" or
 * an array of positive integers. Returns an error string or null.
 */
function validateLessonCards(cards) {
  if (cards === "all") return null;
  if (!Array.isArray(cards)) {
    return 'Lesson "cards" must be an array of positive integers or the string "all"';
  }
  for (let i = 0; i < cards.length; i++) {
    const v = cards[i];
    if (!Number.isInteger(v) || v <= 0) {
      return `Lesson "cards[${i}]" must be a positive integer, got: ${JSON.stringify(v)}`;
    }
  }
  return null;
}


// ═══════════════════════════════════════════
// AUTHENTICATION
// ═══════════════════════════════════════════

/**
 * Authenticate a request using the Authorization: Bearer header.
 *
 * @param {Request} request
 * @param {Object} env
 * @param {"device"|"master"} level - Required auth level
 * @returns {{ ok: boolean, error?: Response, deviceName?: string, deviceKey?: string }}
 */
async function authenticate(request, env, level, corsHeaders) {
  const authHeader = request.headers.get("Authorization");
  if (!authHeader) {
    return {
      ok: false,
      error: jsonResponse({ error: "Authorization header required" }, 401, corsHeaders),
    };
  }

  const parts = authHeader.split(" ");
  if (parts.length !== 2 || parts[0] !== "Bearer" || !parts[1]) {
    return {
      ok: false,
      error: jsonResponse(
        { error: "Authorization header must be: Bearer <token>" },
        401,
        corsHeaders
      ),
    };
  }

  const token = parts[1];

  // --- Master key check ---
  if (level === "master") {
    if (token !== env.MASTER_KEY) {
      // Could be a valid device key trying to access admin — give 403
      if (token.startsWith("dk_")) {
        return {
          ok: false,
          error: jsonResponse(
            { error: "Master key required for admin operations" },
            403,
            corsHeaders
          ),
        };
      }
      return {
        ok: false,
        error: jsonResponse({ error: "Invalid master key" }, 401, corsHeaders),
      };
    }
    return { ok: true, deviceName: "admin (master key)", deviceKey: null };
  }

  // --- Device key check ---
  // Also accept master key for device-level endpoints
  if (token === env.MASTER_KEY) {
    return { ok: true, deviceName: "admin (master key)", deviceKey: null };
  }

  // Must be a device key
  if (!token.startsWith("dk_")) {
    return {
      ok: false,
      error: jsonResponse({ error: "Invalid or revoked device key" }, 401, corsHeaders),
    };
  }

  let devices;
  try {
    devices = await kvGet(env.CARDLISH_KV, "meta:device_keys", {});
  } catch (e) {
    return {
      ok: false,
      error: jsonResponse(
        { error: "Internal server error", details: "KV operation failed" },
        500,
        corsHeaders
      ),
    };
  }

  if (!devices[token]) {
    return {
      ok: false,
      error: jsonResponse({ error: "Invalid or revoked device key" }, 401, corsHeaders),
    };
  }

  // Check if device is blocked
  if (devices[token].status === "blocked") {
    return {
      ok: false,
      error: jsonResponse({ error: "Device has been blocked", blocked: true }, 403, corsHeaders),
    };
  }

  return {
    ok: true,
    deviceName: devices[token].name,
    deviceKey: token,
  };
}

/**
 * Update lastUsed timestamp for a device key.
 * Designed to be called via ctx.waitUntil().
 */
async function updateDeviceLastUsed(kv, deviceKey) {
  if (!deviceKey) return; // master key, nothing to update
  try {
    const devices = await kvGet(kv, "meta:device_keys", {});
    if (devices[deviceKey]) {
      devices[deviceKey].lastUsed = new Date().toISOString();
      await kvPut(kv, "meta:device_keys", devices);
    }
  } catch (_) {
    // Non-critical, silently ignore
  }
}


// ═══════════════════════════════════════════
// DATA HANDLERS — LESSONS
// ═══════════════════════════════════════════

/** GET /api/lessons — return all lessons */
async function getLessons(env, corsHeaders) {
  try {
    const lessons = await kvGet(env.CARDLISH_KV, "data:lessons", []);
    return jsonResponse(lessons, 200, corsHeaders);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }
}

/** PUT /api/lessons — replace all lessons */
async function putLessons(request, env, ctx, corsHeaders, deviceName) {
  const ctErr = checkContentType(request);
  if (ctErr) return jsonResponse({ error: ctErr }, 415, corsHeaders);

  const { data, error } = await safeParseJSON(request);
  if (error) {
    const status = error === "Request body is required" ? 400 : 400;
    return jsonResponse({ error }, status, corsHeaders);
  }

  // Validate: accept { lessons: [...] } or a raw array [...]
  let lessons;
  if (Array.isArray(data)) {
    lessons = data;
  } else if (data && typeof data === "object" && Array.isArray(data.lessons)) {
    lessons = data.lessons;
  } else {
    return jsonResponse(
      { error: "Missing required fields", fields: ["lessons"], hint: 'Body must be { lessons: [...] } or a JSON array' },
      400,
      corsHeaders
    );
  }

  // Validate each lesson
  for (let i = 0; i < lessons.length; i++) {
    const lesson = lessons[i];
    if (!lesson || typeof lesson !== "object") {
      return jsonResponse(
        { error: `lessons[${i}] must be an object` },
        400,
        corsHeaders
      );
    }
    const missing = [];
    if (!lesson.id) missing.push("id");
    if (!lesson.name) missing.push("name");
    if (lesson.cards === undefined) missing.push("cards");
    if (missing.length > 0) {
      return jsonResponse(
        { error: `lessons[${i}] missing required fields`, fields: missing },
        400,
        corsHeaders
      );
    }
    const cardsErr = validateLessonCards(lesson.cards);
    if (cardsErr) {
      return jsonResponse({ error: `lessons[${i}]: ${cardsErr}` }, 400, corsHeaders);
    }
  }

  // Check for duplicate IDs within the submitted array
  const idSet = new Set();
  for (const lesson of lessons) {
    if (idSet.has(lesson.id)) {
      return jsonResponse(
        { error: "Duplicate lesson ID in request", id: lesson.id },
        409,
        corsHeaders
      );
    }
    idSet.add(lesson.id);
  }

  try {
    await kvPut(env.CARDLISH_KV, "data:lessons", lessons);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  ctx.waitUntil(bumpVersion(env.CARDLISH_KV, deviceName));
  return jsonResponse({ ok: true, count: lessons.length }, 200, corsHeaders);
}

/** POST /api/lessons — create one lesson */
async function postLesson(request, env, ctx, corsHeaders, deviceName) {
  const ctErr = checkContentType(request);
  if (ctErr) return jsonResponse({ error: ctErr }, 415, corsHeaders);

  const { data, error } = await safeParseJSON(request);
  if (error) return jsonResponse({ error }, 400, corsHeaders);

  if (!data || typeof data !== "object") {
    return jsonResponse({ error: "Request body must be a JSON object" }, 400, corsHeaders);
  }

  const missing = [];
  if (!data.id) missing.push("id");
  if (!data.name) missing.push("name");
  if (data.cards === undefined) missing.push("cards");
  if (missing.length > 0) {
    return jsonResponse({ error: "Missing required fields", fields: missing }, 400, corsHeaders);
  }

  const cardsErr = validateLessonCards(data.cards);
  if (cardsErr) return jsonResponse({ error: cardsErr }, 400, corsHeaders);

  let lessons;
  try {
    lessons = await kvGet(env.CARDLISH_KV, "data:lessons", []);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  // Check for duplicate ID
  if (lessons.some((l) => l.id === data.id)) {
    return jsonResponse({ error: "Lesson already exists", id: data.id }, 409, corsHeaders);
  }

  lessons.push(data);

  try {
    await kvPut(env.CARDLISH_KV, "data:lessons", lessons);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  ctx.waitUntil(bumpVersion(env.CARDLISH_KV, deviceName));
  return jsonResponse({ ok: true, lesson: data }, 201, corsHeaders);
}

/** PATCH /api/lessons/:id — update one lesson */
async function patchLesson(request, env, ctx, corsHeaders, deviceName, lessonId) {
  const ctErr = checkContentType(request);
  if (ctErr) return jsonResponse({ error: ctErr }, 415, corsHeaders);

  const { data, error } = await safeParseJSON(request);
  if (error) return jsonResponse({ error }, 400, corsHeaders);

  if (!data || typeof data !== "object") {
    return jsonResponse({ error: "Request body must be a JSON object" }, 400, corsHeaders);
  }

  // If cards field is being updated, validate it
  if (data.cards !== undefined) {
    const cardsErr = validateLessonCards(data.cards);
    if (cardsErr) return jsonResponse({ error: cardsErr }, 400, corsHeaders);
  }

  let lessons;
  try {
    lessons = await kvGet(env.CARDLISH_KV, "data:lessons", []);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  const idx = lessons.findIndex((l) => l.id === lessonId);
  if (idx === -1) {
    return jsonResponse({ error: "Lesson not found", id: lessonId }, 404, corsHeaders);
  }

  // If they're trying to change the id, check it doesn't conflict
  if (data.id !== undefined && data.id !== lessonId) {
    if (lessons.some((l) => l.id === data.id)) {
      return jsonResponse({ error: "Lesson already exists", id: data.id }, 409, corsHeaders);
    }
  }

  // Merge fields
  lessons[idx] = { ...lessons[idx], ...data };

  try {
    await kvPut(env.CARDLISH_KV, "data:lessons", lessons);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  ctx.waitUntil(bumpVersion(env.CARDLISH_KV, deviceName));
  return jsonResponse({ ok: true, lesson: lessons[idx] }, 200, corsHeaders);
}

/** DELETE /api/lessons/:id — delete one lesson */
async function deleteLesson(env, ctx, corsHeaders, deviceName, lessonId) {
  // Prevent deleting the "All Cards" lesson
  if (lessonId === "all_cards" || lessonId === "all-cards") {
    return jsonResponse({ error: "Cannot delete the All Cards lesson" }, 403, corsHeaders);
  }

  let lessons;
  try {
    lessons = await kvGet(env.CARDLISH_KV, "data:lessons", []);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  const idx = lessons.findIndex((l) => l.id === lessonId);
  if (idx === -1) {
    return jsonResponse({ error: "Lesson not found", id: lessonId }, 404, corsHeaders);
  }

  // Also guard: if the lesson has cards === "all", it's the All Cards lesson
  if (lessons[idx].cards === "all") {
    return jsonResponse({ error: "Cannot delete the All Cards lesson" }, 403, corsHeaders);
  }

  lessons.splice(idx, 1);

  try {
    await kvPut(env.CARDLISH_KV, "data:lessons", lessons);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  ctx.waitUntil(bumpVersion(env.CARDLISH_KV, deviceName));
  return jsonResponse({ ok: true, deleted: lessonId }, 200, corsHeaders);
}


// ═══════════════════════════════════════════
// DATA HANDLERS — CARDS
// ═══════════════════════════════════════════

/** GET /api/cards — return all cards */
async function getCards(env, corsHeaders) {
  try {
    const cards = await kvGet(env.CARDLISH_KV, "data:cards", []);
    return jsonResponse(cards, 200, corsHeaders);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }
}

/** PUT /api/cards — replace all cards */
async function putCards(request, env, ctx, corsHeaders, deviceName) {
  const ctErr = checkContentType(request);
  if (ctErr) return jsonResponse({ error: ctErr }, 415, corsHeaders);

  const { data, error } = await safeParseJSON(request);
  if (error) return jsonResponse({ error }, 400, corsHeaders);

  if (!Array.isArray(data)) {
    return jsonResponse(
      { error: "Request body must be a JSON array of cards" },
      400,
      corsHeaders
    );
  }

  try {
    await kvPut(env.CARDLISH_KV, "data:cards", data);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  ctx.waitUntil(bumpVersion(env.CARDLISH_KV, deviceName));
  return jsonResponse({ ok: true, count: data.length }, 200, corsHeaders);
}

/** PATCH /api/cards/:card_no — update one card */
async function patchCard(request, env, ctx, corsHeaders, deviceName, cardNo) {
  const ctErr = checkContentType(request);
  if (ctErr) return jsonResponse({ error: ctErr }, 415, corsHeaders);

  const { data, error } = await safeParseJSON(request);
  if (error) return jsonResponse({ error }, 400, corsHeaders);

  if (!data || typeof data !== "object") {
    return jsonResponse({ error: "Request body must be a JSON object" }, 400, corsHeaders);
  }

  // Parse card_no to integer for matching
  const cardNoInt = parseInt(cardNo, 10);
  if (isNaN(cardNoInt) || cardNoInt <= 0) {
    return jsonResponse(
      { error: "Invalid card number, must be a positive integer", card_no: cardNo },
      400,
      corsHeaders
    );
  }

  let cards;
  try {
    cards = await kvGet(env.CARDLISH_KV, "data:cards", []);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  const idx = cards.findIndex((c) => c.card_no === cardNoInt);
  if (idx === -1) {
    return jsonResponse(
      { error: "Card not found", card_no: cardNoInt },
      404,
      corsHeaders
    );
  }

  cards[idx] = { ...cards[idx], ...data };

  try {
    await kvPut(env.CARDLISH_KV, "data:cards", cards);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  ctx.waitUntil(bumpVersion(env.CARDLISH_KV, deviceName));
  return jsonResponse({ ok: true, card: cards[idx] }, 200, corsHeaders);
}


// ═══════════════════════════════════════════
// DATA HANDLERS — VOCAB
// ═══════════════════════════════════════════

/** GET /api/vocab — return all vocab */
async function getVocab(env, corsHeaders) {
  try {
    const vocab = await kvGet(env.CARDLISH_KV, "data:vocab", {});
    return jsonResponse(vocab, 200, corsHeaders);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }
}

/** PUT /api/vocab — replace all vocab */
async function putVocab(request, env, ctx, corsHeaders, deviceName) {
  const ctErr = checkContentType(request);
  if (ctErr) return jsonResponse({ error: ctErr }, 415, corsHeaders);

  const { data, error } = await safeParseJSON(request);
  if (error) return jsonResponse({ error }, 400, corsHeaders);

  if (!data || typeof data !== "object" || Array.isArray(data)) {
    return jsonResponse(
      { error: "Request body must be a JSON object (vocab keyed by pair_id)" },
      400,
      corsHeaders
    );
  }

  try {
    await kvPut(env.CARDLISH_KV, "data:vocab", data);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  ctx.waitUntil(bumpVersion(env.CARDLISH_KV, deviceName));
  return jsonResponse({ ok: true, count: Object.keys(data).length }, 200, corsHeaders);
}

/** PATCH /api/vocab/:pair_id — update vocab for one pair */
async function patchVocab(request, env, ctx, corsHeaders, deviceName, pairId) {
  const ctErr = checkContentType(request);
  if (ctErr) return jsonResponse({ error: ctErr }, 415, corsHeaders);

  // Validate pair_id format: should match pattern like "001_card" or "42_card"
  if (!/^\d+_\w+$/.test(pairId)) {
    return jsonResponse(
      {
        error: "Invalid pair_id format",
        pair_id: pairId,
        expected: "Format: <number>_<suffix> (e.g. 001_card)",
      },
      400,
      corsHeaders
    );
  }

  const { data, error } = await safeParseJSON(request);
  if (error) return jsonResponse({ error }, 400, corsHeaders);

  if (!data || typeof data !== "object") {
    return jsonResponse({ error: "Request body must be a JSON object" }, 400, corsHeaders);
  }

  // Validate that front/back are arrays if provided
  if (data.front !== undefined && !Array.isArray(data.front)) {
    return jsonResponse({ error: '"front" must be an array' }, 400, corsHeaders);
  }
  if (data.back !== undefined && !Array.isArray(data.back)) {
    return jsonResponse({ error: '"back" must be an array' }, 400, corsHeaders);
  }

  let vocab;
  try {
    vocab = await kvGet(env.CARDLISH_KV, "data:vocab", {});
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  // Merge — create if not exists
  vocab[pairId] = { ...(vocab[pairId] || {}), ...data };

  try {
    await kvPut(env.CARDLISH_KV, "data:vocab", vocab);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  ctx.waitUntil(bumpVersion(env.CARDLISH_KV, deviceName));
  return jsonResponse({ ok: true, pair_id: pairId, vocab: vocab[pairId] }, 200, corsHeaders);
}


// ═══════════════════════════════════════════
// DATA HANDLERS — AUDIO MAP
// ═══════════════════════════════════════════

/** GET /api/audio-map — return the audio map */
async function getAudioMap(env, corsHeaders) {
  try {
    const audioMap = await kvGet(env.CARDLISH_KV, "data:audio_map", {
      words: {},
      sentences: {},
    });
    return jsonResponse(audioMap, 200, corsHeaders);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }
}

/** PUT /api/audio-map — replace entire audio map */
async function putAudioMap(request, env, ctx, corsHeaders, deviceName) {
  const ctErr = checkContentType(request);
  if (ctErr) return jsonResponse({ error: ctErr }, 415, corsHeaders);

  const { data, error } = await safeParseJSON(request);
  if (error) return jsonResponse({ error }, 400, corsHeaders);

  if (!data || typeof data !== "object") {
    return jsonResponse(
      { error: "Request body must be a JSON object with words and sentences" },
      400,
      corsHeaders
    );
  }

  try {
    await kvPut(env.CARDLISH_KV, "data:audio_map", data);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  ctx.waitUntil(bumpVersion(env.CARDLISH_KV, deviceName));
  return jsonResponse({ ok: true, count: Object.keys(data).length }, 200, corsHeaders);
}

/** GET /api/version — return version metadata */
async function getVersion(env, corsHeaders) {
  try {
    const version = await kvGet(env.CARDLISH_KV, "meta:version", {
      hash: "none",
      updatedAt: null,
      updatedBy: null,
    });
    return jsonResponse(version, 200, corsHeaders);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }
}


// ═══════════════════════════════════════════
// DEVICE MANAGEMENT (Admin)
// ═══════════════════════════════════════════

/** GET /api/admin/devices — list all device keys */
async function listDevices(env, corsHeaders) {
  try {
    const devices = await kvGet(env.CARDLISH_KV, "meta:device_keys", {});
    return jsonResponse(devices, 200, corsHeaders);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }
}

/** POST /api/admin/devices — create a new device key */
async function createDevice(request, env, corsHeaders) {
  const ctErr = checkContentType(request);
  if (ctErr) return jsonResponse({ error: ctErr }, 415, corsHeaders);

  const { data, error } = await safeParseJSON(request);
  if (error) return jsonResponse({ error }, 400, corsHeaders);

  if (!data || typeof data !== "object") {
    return jsonResponse({ error: "Request body must be a JSON object" }, 400, corsHeaders);
  }

  if (!data.name || typeof data.name !== "string" || data.name.trim() === "") {
    return jsonResponse(
      { error: "Missing required fields", fields: ["name"], hint: 'Body must be { name: "Device name" }' },
      400,
      corsHeaders
    );
  }

  // Generate key: dk_ + 16 random hex chars
  const uuid = crypto.randomUUID().replace(/-/g, "");
  const key = `dk_${uuid.slice(0, 16)}`;

  let devices;
  try {
    devices = await kvGet(env.CARDLISH_KV, "meta:device_keys", {});
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  devices[key] = {
    name: data.name.trim(),
    createdAt: new Date().toISOString(),
    lastUsed: null,
  };

  try {
    await kvPut(env.CARDLISH_KV, "meta:device_keys", devices);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  return jsonResponse({ ok: true, key, name: data.name.trim() }, 201, corsHeaders);
}

/** DELETE /api/admin/devices/:key — revoke a device key */
async function deleteDevice(env, corsHeaders, deviceKey) {
  if (!deviceKey || !deviceKey.startsWith("dk_")) {
    return jsonResponse(
      { error: "Invalid device key format", key: deviceKey },
      400,
      corsHeaders
    );
  }

  let devices;
  try {
    devices = await kvGet(env.CARDLISH_KV, "meta:device_keys", {});
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  if (!devices[deviceKey]) {
    return jsonResponse({ error: "Device not found", key: deviceKey }, 404, corsHeaders);
  }

  const deletedName = devices[deviceKey].name;
  delete devices[deviceKey];

  try {
    await kvPut(env.CARDLISH_KV, "meta:device_keys", devices);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  return jsonResponse({ ok: true, deleted: deviceKey, name: deletedName }, 200, corsHeaders);
}

/** PATCH /api/admin/devices/:key — block or unblock a device */
async function patchDevice(request, env, corsHeaders, deviceKey) {
  if (!deviceKey || !deviceKey.startsWith("dk_")) {
    return jsonResponse(
      { error: "Invalid device key format", key: deviceKey },
      400,
      corsHeaders
    );
  }

  const ctErr = checkContentType(request);
  if (ctErr) return jsonResponse({ error: ctErr }, 415, corsHeaders);

  const { data, error } = await safeParseJSON(request);
  if (error) return jsonResponse({ error }, 400, corsHeaders);

  if (!data || !data.status || !["active", "blocked"].includes(data.status)) {
    return jsonResponse(
      { error: "Invalid status", hint: 'Body must be { status: "active" | "blocked" }' },
      400,
      corsHeaders
    );
  }

  let devices;
  try {
    devices = await kvGet(env.CARDLISH_KV, "meta:device_keys", {});
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  if (!devices[deviceKey]) {
    return jsonResponse({ error: "Device not found", key: deviceKey }, 404, corsHeaders);
  }

  devices[deviceKey].status = data.status;

  try {
    await kvPut(env.CARDLISH_KV, "meta:device_keys", devices);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  return jsonResponse({ ok: true, key: deviceKey, status: data.status, name: devices[deviceKey].name }, 200, corsHeaders);
}

// ═══════════════════════════════════════════
// SELF-REGISTRATION
// ═══════════════════════════════════════════

/**
 * Check rate limit for device registration.
 * Uses KV with TTL to track registrations per IP.
 * Returns true if under limit, false if exceeded.
 */
async function checkRegisterRateLimit(kv, ip, maxPerHour) {
  const key = `ratelimit:register:${ip}`;
  try {
    const raw = await kv.get(key);
    const count = raw ? parseInt(raw, 10) : 0;
    if (count >= maxPerHour) return false;
    // Increment counter with 1-hour TTL
    await kv.put(key, String(count + 1), { expirationTtl: 3600 });
    return true;
  } catch {
    // On KV error, allow the request (fail open)
    return true;
  }
}

/** POST /api/register — self-register a new device (no auth required) */
async function registerDevice(request, env, corsHeaders) {
  const ctErr = checkContentType(request);
  if (ctErr) return jsonResponse({ error: ctErr }, 415, corsHeaders);

  const { data, error } = await safeParseJSON(request);
  if (error) return jsonResponse({ error }, 400, corsHeaders);

  if (!data || typeof data !== "object") {
    return jsonResponse({ error: "Request body required" }, 400, corsHeaders);
  }

  // Validate app secret
  if (!data.appSecret || data.appSecret !== env.APP_SECRET) {
    return jsonResponse({ error: "Invalid app secret" }, 403, corsHeaders);
  }

  // Rate limit by IP
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const maxPerHour = parseInt(env.REGISTER_RATE_LIMIT || "5", 10);
  const allowed = await checkRegisterRateLimit(env.CARDLISH_KV, ip, maxPerHour);
  if (!allowed) {
    return jsonResponse(
      { error: "Too many registrations. Try again later.", retryAfter: 3600 },
      429,
      corsHeaders
    );
  }

  // Build device name from provided info or default
  const deviceInfo = (data.deviceInfo || "").trim();
  const deviceName = deviceInfo || `Device ${new Date().toISOString().slice(0, 10)}`;

  // Generate device key
  const key = "dk_" + crypto.randomUUID().replace(/-/g, "").slice(0, 16);

  let devices;
  try {
    devices = await kvGet(env.CARDLISH_KV, "meta:device_keys", {});
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  devices[key] = {
    name: deviceName,
    createdAt: new Date().toISOString(),
    lastUsed: null,
    status: "active",
    registeredBy: "self",
    ip: ip,
    userAgent: (request.headers.get("User-Agent") || "").slice(0, 200),
  };

  try {
    await kvPut(env.CARDLISH_KV, "meta:device_keys", devices);
  } catch (e) {
    return jsonResponse(
      { error: "Internal server error", details: "KV operation failed" },
      500,
      corsHeaders
    );
  }

  return jsonResponse({ ok: true, key, name: deviceName }, 201, corsHeaders);
}


// ═══════════════════════════════════════════
// ROUTER
// ═══════════════════════════════════════════

/**
 * Main router — matches URL path and method to the correct handler.
 * Returns a Response or null (for 404).
 */
async function handleRequest(request, env, ctx) {
  const corsHeaders = buildCorsHeaders(request, env);

  // --- OPTIONS preflight ---
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  const url = new URL(request.url);
  const path = url.pathname;
  const method = request.method;
  const segments = pathSegments(request.url);

  // --- Health Check ---
  // GET /api/health
  if (path === "/api/health" || (segments.length === 2 && segments[0] === "api" && segments[1] === "health")) {
    if (method !== "GET") {
      return jsonResponse(
        { error: "Method not allowed", allowed: ["GET"] },
        405,
        corsHeaders
      );
    }
    return jsonResponse(
      { status: "ok", timestamp: new Date().toISOString() },
      200,
      corsHeaders
    );
  }

  // --- Public GET endpoints ---

  // GET /api/lessons
  if (path === "/api/lessons" && method === "GET") {
    return getLessons(env, corsHeaders);
  }

  // GET /api/cards
  if (path === "/api/cards" && method === "GET") {
    return getCards(env, corsHeaders);
  }

  // GET /api/vocab
  if (path === "/api/vocab" && method === "GET") {
    return getVocab(env, corsHeaders);
  }

  // GET /api/audio-map
  if (path === "/api/audio-map" && method === "GET") {
    return getAudioMap(env, corsHeaders);
  }

  // GET /api/version
  if (path === "/api/version" && method === "GET") {
    return getVersion(env, corsHeaders);
  }

  // --- Protected endpoints (device key auth) ---

  // /api/lessons (PUT, POST)
  if (path === "/api/lessons" && (method === "PUT" || method === "POST")) {
    const auth = await authenticate(request, env, "device", corsHeaders);
    if (!auth.ok) return auth.error;
    ctx.waitUntil(updateDeviceLastUsed(env.CARDLISH_KV, auth.deviceKey));

    if (method === "PUT") return putLessons(request, env, ctx, corsHeaders, auth.deviceName);
    if (method === "POST") return postLesson(request, env, ctx, corsHeaders, auth.deviceName);
  }

  // /api/lessons — method not allowed for non GET/PUT/POST
  if (path === "/api/lessons") {
    return jsonResponse(
      { error: "Method not allowed", allowed: ["GET", "PUT", "POST"] },
      405,
      corsHeaders
    );
  }

  // /api/lessons/:id (PATCH, DELETE)
  if (segments.length === 3 && segments[0] === "api" && segments[1] === "lessons") {
    const lessonId = decodeURIComponent(segments[2]);

    if (method === "GET") {
      // Convenience: get single lesson
      try {
        const lessons = await kvGet(env.CARDLISH_KV, "data:lessons", []);
        const lesson = lessons.find((l) => l.id === lessonId);
        if (!lesson) return jsonResponse({ error: "Lesson not found", id: lessonId }, 404, corsHeaders);
        return jsonResponse(lesson, 200, corsHeaders);
      } catch (e) {
        return jsonResponse({ error: "Internal server error", details: "KV operation failed" }, 500, corsHeaders);
      }
    }

    if (method !== "PATCH" && method !== "DELETE") {
      return jsonResponse(
        { error: "Method not allowed", allowed: ["GET", "PATCH", "DELETE"] },
        405,
        corsHeaders
      );
    }

    const auth = await authenticate(request, env, "device", corsHeaders);
    if (!auth.ok) return auth.error;
    ctx.waitUntil(updateDeviceLastUsed(env.CARDLISH_KV, auth.deviceKey));

    if (method === "PATCH") return patchLesson(request, env, ctx, corsHeaders, auth.deviceName, lessonId);
    if (method === "DELETE") return deleteLesson(env, ctx, corsHeaders, auth.deviceName, lessonId);
  }

  // /api/cards (PUT)
  if (path === "/api/cards" && method === "PUT") {
    const auth = await authenticate(request, env, "device", corsHeaders);
    if (!auth.ok) return auth.error;
    ctx.waitUntil(updateDeviceLastUsed(env.CARDLISH_KV, auth.deviceKey));
    return putCards(request, env, ctx, corsHeaders, auth.deviceName);
  }

  // /api/cards — method not allowed for non GET/PUT
  if (path === "/api/cards") {
    return jsonResponse(
      { error: "Method not allowed", allowed: ["GET", "PUT"] },
      405,
      corsHeaders
    );
  }

  // /api/cards/:card_no (PATCH)
  if (segments.length === 3 && segments[0] === "api" && segments[1] === "cards") {
    const cardNo = segments[2];

    if (method !== "PATCH") {
      return jsonResponse(
        { error: "Method not allowed", allowed: ["PATCH"] },
        405,
        corsHeaders
      );
    }

    const auth = await authenticate(request, env, "device", corsHeaders);
    if (!auth.ok) return auth.error;
    ctx.waitUntil(updateDeviceLastUsed(env.CARDLISH_KV, auth.deviceKey));
    return patchCard(request, env, ctx, corsHeaders, auth.deviceName, cardNo);
  }

  // /api/vocab (PUT)
  if (path === "/api/vocab" && method === "PUT") {
    const auth = await authenticate(request, env, "device", corsHeaders);
    if (!auth.ok) return auth.error;
    ctx.waitUntil(updateDeviceLastUsed(env.CARDLISH_KV, auth.deviceKey));
    return putVocab(request, env, ctx, corsHeaders, auth.deviceName);
  }

  // /api/vocab — method not allowed for non GET/PUT
  if (path === "/api/vocab") {
    return jsonResponse(
      { error: "Method not allowed", allowed: ["GET", "PUT"] },
      405,
      corsHeaders
    );
  }

  // /api/vocab/:pair_id (PATCH)
  if (segments.length === 3 && segments[0] === "api" && segments[1] === "vocab") {
    const pairId = decodeURIComponent(segments[2]);

    if (method !== "PATCH") {
      return jsonResponse(
        { error: "Method not allowed", allowed: ["PATCH"] },
        405,
        corsHeaders
      );
    }

    const auth = await authenticate(request, env, "device", corsHeaders);
    if (!auth.ok) return auth.error;
    ctx.waitUntil(updateDeviceLastUsed(env.CARDLISH_KV, auth.deviceKey));
    return patchVocab(request, env, ctx, corsHeaders, auth.deviceName, pairId);
  }

  // /api/audio-map (PUT)
  if (path === "/api/audio-map" && method === "PUT") {
    const auth = await authenticate(request, env, "device", corsHeaders);
    if (!auth.ok) return auth.error;
    ctx.waitUntil(updateDeviceLastUsed(env.CARDLISH_KV, auth.deviceKey));
    return putAudioMap(request, env, ctx, corsHeaders, auth.deviceName);
  }

  // /api/audio-map — method not allowed for non GET/PUT
  if (path === "/api/audio-map") {
    return jsonResponse(
      { error: "Method not allowed", allowed: ["GET", "PUT"] },
      405,
      corsHeaders
    );
  }

  // /api/version — method not allowed for non GET
  if (path === "/api/version") {
    return jsonResponse(
      { error: "Method not allowed", allowed: ["GET"] },
      405,
      corsHeaders
    );
  }

  // --- Self-registration (no auth) ---

  // POST /api/register
  if (path === "/api/register" && method === "POST") {
    return registerDevice(request, env, corsHeaders);
  }
  if (path === "/api/register") {
    return jsonResponse(
      { error: "Method not allowed", allowed: ["POST"] },
      405,
      corsHeaders
    );
  }

  // --- Admin endpoints (master key auth) ---

  // /api/admin/devices
  if (path === "/api/admin/devices") {
    if (method !== "GET" && method !== "POST") {
      return jsonResponse(
        { error: "Method not allowed", allowed: ["GET", "POST"] },
        405,
        corsHeaders
      );
    }

    const auth = await authenticate(request, env, "master", corsHeaders);
    if (!auth.ok) return auth.error;

    if (method === "GET") return listDevices(env, corsHeaders);
    if (method === "POST") return createDevice(request, env, corsHeaders);
  }

  // /api/admin/devices/:key
  if (segments.length === 4 && segments[0] === "api" && segments[1] === "admin" && segments[2] === "devices") {
    const deviceKey = decodeURIComponent(segments[3]);

    if (method !== "DELETE" && method !== "PATCH") {
      return jsonResponse(
        { error: "Method not allowed", allowed: ["DELETE", "PATCH"] },
        405,
        corsHeaders
      );
    }

    const auth = await authenticate(request, env, "master", corsHeaders);
    if (!auth.ok) return auth.error;

    if (method === "DELETE") return deleteDevice(env, corsHeaders, deviceKey);
    if (method === "PATCH") return patchDevice(request, env, corsHeaders, deviceKey);
  }

  // --- 404: Unknown route ---
  return jsonResponse({ error: "Not found", path: path }, 404, corsHeaders);
}


// ═══════════════════════════════════════════
// MAIN EXPORT
// ═══════════════════════════════════════════

export default {
  async fetch(request, env, ctx) {
    try {
      return await handleRequest(request, env, ctx);
    } catch (e) {
      // Top-level catch for truly unexpected errors
      const corsHeaders = buildCorsHeaders(request, env);
      console.error("Unhandled error:", e.message, e.stack);
      return jsonResponse(
        {
          error: "Internal server error",
          details: e.message || "An unexpected error occurred",
        },
        500,
        corsHeaders
      );
    }
  },
};
