# Cardlish Learn - Build & Deploy Rules

## Project Structure

```
src/                    -> dist/              (HTML, CSS, JS - PRODUCTION)
unified_db/cards/*.png  -> dist/cards/        (card images)
public/audio/           -> dist/audio/        (card audio, FLAT)
public/audio/vocab/     -> dist/audio/vocab/  (word pronunciation, 330 MP3s)
public/audio/sentences/ -> dist/audio/sentences/ (sentence audio, 106 MP3s)
public/data/*.json      -> dist/data/         (cards, vocab, lessons, audio map)
```

### Key Directories

| Directory | Purpose | Editable? |
|-----------|---------|-----------|
| `src/` | Production web app (app.js, index.html, styles.css) | ✅ Yes |
| `public/data/` | Source JSON data (cards, vocab, lessons) | ✅ Yes |
| `public/audio/` | Source audio files (3 subdirs) | ⚠️ Via scripts only |
| `unified_db/cards/` | Card images (PNG) | ⚠️ Via pipeline only |
| `dist/` | **BUILD OUTPUT — NEVER edit directly** | 🚫 NO |
| `admin/` | Admin UI (dev tools) | ✅ Yes |
| `scripts/` | Build, deploy, validation scripts | ✅ Yes |
| `tools/` | Print vocab cards, generate PDFs | ✅ Yes |
| `experiments/` | OCR & vocab extraction pipeline | ✅ Yes |
| `core/` | Python pipeline modules (PDF→grid→QR→OCR→pair) | ⚠️ Careful |
| `pdf_cards/` | Generated PDF output (tracked in git) | ✅ Yes |

## Build Commands

```bash
python scripts/build_deploy.py --validate   # Check sources (no build)
python scripts/build_deploy.py -o dist      # Full build with validation
```

The build script automatically:
- Validates source files (pre-build)
- Copies all assets recursively (including audio subdirs)
- Rewrites CONFIG paths in app.js for production
- Generates content-based cache-bust hashes for CSS/JS
- Validates dist/ output (post-build)

---

## 🃏 Card Processing Pipeline

### Full Flow: PDF → Cards → OCR → Vocab → Audio

```
PDF scan  →  split_cardlish_pdf.py / batch_split.py    →  unified_db/cards/
          →  scripts/build_manifest.py                  →  public/data/cards.json
          →  experiments/run_ocr_all_cards.py            →  experiments/raw_ocr_results.json
          →  experiments/extract_vocab_v3.py             →  public/data/cards_vocab.json
          →  experiments/clean_vocab_final.py            →  public/data/cards_vocab.json (cleaned)
          →  scripts/generate_vocab_audio.py             →  public/audio/vocab/ + sentences/
          →  scripts/build_deploy.py -o dist             →  dist/ (ready to deploy)
```

### Pipeline Commands (Incremental — skip already-processed)

```bash
# Step 1: Scan new PDFs (skip already-scanned)
python batch_split.py                              # Auto-skip processed PDFs
python batch_split.py --force                      # Reprocess all PDFs

# Step 2: OCR vocab on card images (skip already-OCR'd)
python experiments/run_ocr_all_cards.py            # Only new cards
python experiments/run_ocr_all_cards.py --cards 1,5 # Re-OCR specific cards
python experiments/run_ocr_all_cards.py --force     # Re-OCR everything

# Step 3: Extract vocab from OCR (skip already-extracted)
python experiments/extract_vocab_v3.py             # Only new cards
python experiments/extract_vocab_v3.py --cards 1,5  # Re-extract specific
python experiments/extract_vocab_v3.py --force      # Re-extract all

# Step 4: Clean OCR errors
python experiments/clean_vocab_final.py

# Step 5: Generate audio for new vocab words
python scripts/generate_vocab_audio.py

# Step 6: Build
python scripts/build_deploy.py -o dist
```

### Pipeline Safety Rules

1. **Pipeline is INCREMENTAL by default** — only processes new/unprocessed cards
2. **Use `--cards X` to re-process specific cards** — for fixing OCR errors
3. **Use `--force` to re-process everything** — use sparingly, overwrites existing data
4. **`clean_vocab_final.py` fixes known OCR errors** — edit this file to add new corrections
5. **NEVER run `extract_vocab_v3.py --force` without running `clean_vocab_final.py` after** — or cleaned data is lost

### Tools (Standalone, NOT deployed)

| Tool | URL (local) | Purpose |
|------|-------------|--------|
| Print vocab cards | `http://localhost:8787/tools/print-vocab-cards.html` | A4 flashcard printing (9 per page) |
| Generate PDFs | `python tools/generate_pdf_cards.py --all` | Batch PDF via headless Chrome |

---

## ⛔ DEPLOY RULES — READ CAREFULLY

### Git Branches

| Branch | Purpose | Cloudflare URL |
|--------|---------|----------------|
| `main` | **PRODUCTION — stable releases only** | `cardlish-learn.pages.dev` |
| `dev` | **Development — daily work happens here** | `dev.cardlish-learn.pages.dev` |

**You are almost always on branch `dev`.** Check with `git branch --show-current`.

### Deploy Commands

| Target | Command | When to use |
|--------|---------|-------------|
| **Dev preview** | `npx wrangler pages deploy dist --branch dev` | After any code change, for testing |
| **Production** | `npx wrangler pages deploy dist --branch main` | **ONLY when user explicitly says "deploy production"** |

### 🚫 DEPLOY SAFETY RULES

1. **NEVER deploy to production unless the user EXPLICITLY says "deploy production" or "deploy lên production".**
   - "deploy" alone means → deploy to **dev**
   - "deploy thử" / "deploy xem" → deploy to **dev**
   - "deploy lại" → deploy to **dev** (unless user specifies production)
   - "deploy production" / "deploy lên trang chính" → deploy to **production**

2. **NEVER run `npx wrangler pages deploy dist` without `--branch`.**
   - Without `--branch`, wrangler uses the current git branch name
   - Since we're on `dev`, it will deploy to dev alias — but this is UNRELIABLE
   - **ALWAYS specify `--branch dev` or `--branch main` explicitly**

3. **NEVER use `python scripts/build_deploy.py --deploy`.**
   - This flag calls wrangler WITHOUT `--branch` — unsafe!
   - Always build and deploy as separate steps

4. **Before deploying production, ALWAYS:**
   - Confirm with user: "Bạn muốn deploy lên PRODUCTION (cardlish-learn.pages.dev)?"
   - Run `git status` to check for uncommitted changes
   - Run `python scripts/build_deploy.py -o dist` to build fresh

5. **NEVER deploy uncommitted experimental changes to production.**
   - If there are uncommitted changes in src/, stash them first: `git stash`
   - Build from clean commit, deploy, then `git stash pop`

---

## CRITICAL RULES

1. **NEVER manually copy files into dist/** — always use the build script
2. **NEVER replace dist/data/cards.json** with `unified_db/data/cards_manifest.json`
   - The manifest has `audio.status='pending'` and empty `local_path`
   - This will silently break ALL audio playback
   - Source of truth: `public/data/cards.json` (has `audio.status='downloaded'`)
3. **ALWAYS run the build script from project root**
4. **Audio has 3 levels** — root (card audio), vocab/, sentences/
   - If build shows only ~53 audio files, the subdirectories are not being copied
   - Correct build shows ~489 files (53 + 330 + 106)

## Dev Server

```bash
python admin_server.py            # Start local server at http://localhost:8787
```

- Serves project root as static files + admin API
- Print vocab cards: `http://localhost:8787/tools/print-vocab-cards.html`
- Admin UI: `http://localhost:8787/admin/`
- **This server is for LOCAL DEV only — never expose to internet**

## TV Browser Constraints

The app runs on Smart TVs (Tizen/WebOS). Key constraints:
- Single Audio element only (`sharedAudio` singleton)
- No `speechSynthesis` (crashes TV browsers, guarded by `IS_TV_BROWSER`)
- No `backdrop-filter: blur()` on TV (disabled in CSS >=1400px media query)
- Max 3 concurrent fetch requests (in `preloadLessonAudio`)
- No touch events on TV (guarded by `'ontouchstart' in window`)

---

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **cardlish_split_mvp** (447 symbols, 1095 relationships, 35 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/cardlish_split_mvp/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/cardlish_split_mvp/context` | Codebase overview, check index freshness |
| `gitnexus://repo/cardlish_split_mvp/clusters` | All functional areas |
| `gitnexus://repo/cardlish_split_mvp/processes` | All execution flows |
| `gitnexus://repo/cardlish_split_mvp/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
