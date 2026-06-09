#!/usr/bin/env python3
"""
Cardlish Admin Server — Local API + static file server.

Serves the Review Editor admin UI and provides API endpoints
for editing card data, vocabulary, and generating audio.

Usage:
    python admin_server.py [--port 8787]
    → Open http://localhost:8787/admin/
"""

import asyncio
import hashlib
import io
import json
import os
import re
import sys
import threading
from datetime import datetime
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

# Fix Windows console encoding
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Paths ─────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
CARDS_JSON = PROJECT_ROOT / "public" / "data" / "cards.json"
VOCAB_JSON = PROJECT_ROOT / "public" / "data" / "cards_vocab.json"
AUDIO_MAP_JSON = PROJECT_ROOT / "public" / "data" / "vocab_audio_map.json"
OVERRIDES_JSON = PROJECT_ROOT / "unified_db" / "data" / "review_overrides.json"
CHANGELOG_JSON = PROJECT_ROOT / "unified_db" / "data" / "change_log.json"
MANIFEST_JSON = PROJECT_ROOT / "unified_db" / "data" / "cards_manifest.json"
VOCAB_AUDIO_DIR = PROJECT_ROOT / "public" / "audio" / "vocab"
SENTENCE_AUDIO_DIR = PROJECT_ROOT / "public" / "audio" / "sentences"

# ── edge-tts config (match generate_vocab_audio.py) ───────
VOICE = "en-US-AnaNeural"
WORD_RATE = "-20%"
SENTENCE_RATE = "-15%"
PITCH = "+5Hz"

DEFAULT_PORT = 8787


# ── Helpers ───────────────────────────────────────────────
def read_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def strip_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text)


def safe_filename(word: str) -> str:
    name = word.lower().strip()
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^a-z0-9_\-]', '', name)
    return name


def sentence_hash(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:12]


def append_changelog(action: str, pair_id: str, changes: dict = None, source: str = "admin_server"):
    log = read_json(CHANGELOG_JSON) or []
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "pair_id": pair_id,
        "source": source,
    }
    if changes:
        entry["changes"] = changes
    log.append(entry)
    write_json(CHANGELOG_JSON, log)


# ── Audio Generation ──────────────────────────────────────
async def generate_single_audio(text: str, output_path: str, rate: str):
    """Generate a single MP3 using edge-tts."""
    import edge_tts
    communicate = edge_tts.Communicate(text=text, voice=VOICE, rate=rate, pitch=PITCH)
    await communicate.save(output_path)


def generate_audio_sync(words: list, sentences: list) -> dict:
    """Generate audio for given words and sentences. Returns result dict."""
    result = {"generated": {"words": {}, "sentences": {}}, "skipped": {}, "errors": []}

    VOCAB_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    SENTENCE_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing audio map
    audio_map = read_json(AUDIO_MAP_JSON) or {"words": {}, "sentences": {}}

    async def run():
        # Generate word audio
        for word in words:
            word_lower = word.lower().strip()
            if not word_lower:
                continue
            filename = f"{safe_filename(word_lower)}.mp3"
            output_path = VOCAB_AUDIO_DIR / filename
            relative_path = f"audio/vocab/{filename}"

            if output_path.exists():
                result["skipped"][word_lower] = relative_path
                audio_map["words"][word_lower] = relative_path
                continue

            try:
                await generate_single_audio(word, str(output_path), rate=WORD_RATE)
                result["generated"]["words"][word_lower] = relative_path
                audio_map["words"][word_lower] = relative_path
                await asyncio.sleep(0.3)
            except Exception as e:
                result["errors"].append(f"Word '{word}': {e}")

        # Generate sentence audio
        for sentence in sentences:
            plain = strip_html(sentence).strip()
            if not plain:
                continue
            h = sentence_hash(plain)
            filename = f"{h}.mp3"
            output_path = SENTENCE_AUDIO_DIR / filename
            relative_path = f"audio/sentences/{filename}"

            if output_path.exists():
                result["skipped"][plain] = relative_path
                audio_map["sentences"][plain] = relative_path
                continue

            try:
                await generate_single_audio(plain, str(output_path), rate=SENTENCE_RATE)
                result["generated"]["sentences"][plain] = relative_path
                audio_map["sentences"][plain] = relative_path
                await asyncio.sleep(0.3)
            except Exception as e:
                result["errors"].append(f"Sentence: {e}")

    asyncio.run(run())

    # Save updated audio map
    write_json(AUDIO_MAP_JSON, audio_map)
    return result


# ── API Handlers ──────────────────────────────────────────
def handle_api(handler, method: str, path: str, body: bytes = b""):
    """Route API requests. Returns (status_code, response_dict)."""

    # GET /api/cards
    if method == "GET" and path == "/api/cards":
        data = read_json(CARDS_JSON)
        return (200, data) if data else (404, {"error": "cards.json not found"})

    # GET /api/vocab
    if method == "GET" and path == "/api/vocab":
        data = read_json(VOCAB_JSON)
        return (200, data) if data else (404, {"error": "cards_vocab.json not found"})

    # GET /api/overrides
    if method == "GET" and path == "/api/overrides":
        data = read_json(OVERRIDES_JSON)
        return (200, data) if data else (200, {"_version": 1, "_updated_at": "", "overrides": {}})

    # GET /api/audio-map
    if method == "GET" and path == "/api/audio-map":
        data = read_json(AUDIO_MAP_JSON)
        return (200, data) if data else (200, {"words": {}, "sentences": {}})

    # POST /api/patch — apply card metadata overrides
    if method == "POST" and path == "/api/patch":
        try:
            patch = json.loads(body)
            overrides_data = read_json(OVERRIDES_JSON) or {"_version": 1, "_updated_at": "", "overrides": {}}
            patch_overrides = patch.get("overrides", {})

            allowed = {"card_no", "label", "qr_url", "needs_review", "review_note",
                        "manual_locked", "front_image", "back_image", "hidden"}
            count = 0
            for pair_id, fields in patch_overrides.items():
                clean = {k: v for k, v in fields.items() if k in allowed}
                if not clean:
                    continue
                existing = overrides_data["overrides"].get(pair_id, {})
                existing.update(clean)
                overrides_data["overrides"][pair_id] = existing
                append_changelog("override", pair_id, clean)
                count += 1

            overrides_data["_updated_at"] = datetime.now().isoformat()
            write_json(OVERRIDES_JSON, overrides_data)
            return (200, {"applied": count})
        except Exception as e:
            return (400, {"error": str(e)})

    # PUT /api/vocab/<pair_id> — save vocab for one card
    if method == "PUT" and path.startswith("/api/vocab/"):
        pair_id = path.split("/api/vocab/", 1)[1]
        if not pair_id:
            return (400, {"error": "Missing pair_id"})
        try:
            new_vocab = json.loads(body)
            all_vocab = read_json(VOCAB_JSON) or {}
            all_vocab[pair_id] = new_vocab
            write_json(VOCAB_JSON, all_vocab)
            append_changelog("vocab_edit", pair_id, {"fields": list(new_vocab.keys())})
            return (200, {"saved": pair_id})
        except Exception as e:
            return (400, {"error": str(e)})

    # POST /api/generate-audio — trigger edge-tts
    if method == "POST" and path == "/api/generate-audio":
        try:
            req = json.loads(body)
            words = req.get("words", [])
            sentences = req.get("sentences", [])
            if not words and not sentences:
                return (400, {"error": "No words or sentences provided"})

            print(f"  🔊 Generating audio: {len(words)} words, {len(sentences)} sentences...")
            result = generate_audio_sync(words, sentences)
            gen_w = len(result["generated"]["words"])
            gen_s = len(result["generated"]["sentences"])
            skip = len(result["skipped"])
            print(f"  ✅ Generated {gen_w} words + {gen_s} sentences, skipped {skip}")
            return (200, result)
        except Exception as e:
            return (500, {"error": str(e)})

    return (404, {"error": f"Unknown API: {method} {path}"})


# ── HTTP Handler ──────────────────────────────────────────
class AdminHandler(SimpleHTTPRequestHandler):
    """Custom handler: API routes + static file serving."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            status, data = handle_api(self, "GET", path)
            self._send_json(status, data)
        else:
            # Serve static files
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        if path.startswith("/api/"):
            status, data = handle_api(self, "POST", path, body)
            self._send_json(status, data)
        else:
            self._send_json(404, {"error": "Not found"})

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        if path.startswith("/api/"):
            status, data = handle_api(self, "PUT", path, body)
            self._send_json(status, data)
        else:
            self._send_json(404, {"error": "Not found"})

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def _send_json(self, status: int, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format, *args):
        # Quieter logging — only show API calls and errors
        msg = format % args
        if "/api/" in msg or "404" in msg or "500" in msg:
            print(f"  {msg}")


# ── Main ──────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cardlish Admin Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port (default: {DEFAULT_PORT})")
    args = parser.parse_args()

    port = args.port
    server = HTTPServer(("", port), AdminHandler)

    print("=" * 56)
    print("  ✦ Cardlish Admin Server")
    print("=" * 56)
    print(f"  📂 Project: {PROJECT_ROOT}")
    print(f"  🌐 Admin:   http://localhost:{port}/admin/")
    print(f"  📡 API:     http://localhost:{port}/api/")
    print(f"  ⌨️  Ctrl+C to stop")
    print("=" * 56)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  👋 Server stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
