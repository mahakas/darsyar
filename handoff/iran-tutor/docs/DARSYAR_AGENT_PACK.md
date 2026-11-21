# DARSYAR (iran-tutor) — Master Upgrade & Modular Expansion Pack

> **Target Repository:** `mahakas/iran-tutor` (FastAPI + PostgreSQL + Qdrant + Redis + Next.js 16 RTL)
> **Execution Rule:** Execute strictly **ONE PHASE AT A TIME**. Do NOT skip phases. At the start of every phase, inspect existing files and run existing tests before writing new code. Never break existing functionality.

---

## 0. Non-Negotiable Architectural & Product Rules

1. **Web App Only (No Desktop / No CLI / No IM Bots):**
   - Everything MUST run inside the existing FastAPI backend and Next.js RTL web frontend.
   - Do NOT add Tauri/Electron desktop wrappers, CLI tools, terminal subagents, or Telegram/Discord bots.

2. **Strict Admin Governance (Centralized Control):**
   - The app is strictly split into **Admin (`/admin`)** and **Student/User** areas.
   - **ONLY Admins** can configure AI Providers, API keys (stored encrypted at rest), Embedding models, Per-Feature Model Routing, Quotas, Feature Flags, Skills/Prompts, and official Knowledge Bases.
   - Students MUST NEVER see, input, or override raw API keys, provider URLs, or model configs.

3. **Glass-Box Admin Observability ("Nothing Hidden from Admin"):**
   - Every single AI call, prompt/response, token count, estimated cost, latency, RAG retrieval citations (or RAG misses), uploaded image/audio, student quiz attempt, flashcard deck, and learner memory node MUST be logged and inspectable in `/admin`.

4. **Modular Extensibility (Plugin-Ready Architecture):**
   - Every learning feature (existing Chat/Quiz and new Flashcards, Notebook, Immersive Reader, Visualize, etc.) MUST route through a single **Shared Capability Runtime** + **Central AI Gateway** + **Capability Registry** + **Typed Learning Blocks** schema.
   - Preserve `.kilocode/rules/architecture.md` and Iranian textbook fidelity: ground academic answers in official textbook chapters/printed page numbers and never hallucinate outside retrieved sources when textbook mode is active.

5. **RTL Persian UX:**
   - All student & admin UI text, validation messages, dates/labels, and math/LaTeX rendering (KaTeX/MathJax RTL-safe) must work cleanly in Persian RTL.

---

## PHASE 0 — Codebase Audit & Baseline Verification

### Objectives
Map the existing `iran-tutor` codebase before modifying anything.

### Tasks
1. Read `.kilocode/rules/architecture.md`, `docker-compose.yml`, `backend/` structure, `alembic/` migrations, `scripts/ingest_book.py`, and `frontend/` routes/components.
2. Run existing backend tests (`pytest`) and frontend typecheck/build (`npm run build` / `tsc --noEmit`) to establish a clean baseline.
3. Produce `docs/PHASE0_INVENTORY.md` documenting:
   - Existing database tables & SQLAlchemy models
   - Existing API endpoints (`/api/v1/...`)
   - Existing LLM/Vision/STT/Qdrant client calls (all places that must be refactored into the Central AI Gateway)
   - Current `/admin` and student pages
   - Demo/SQLite compatibility behavior (if present) so migrations don't break local dev.

### Verification Gate (Stop & Report)
- Existing tests and frontend build pass.
- `docs/PHASE0_INVENTORY.md` created and accurate.

---

## PHASE 1 — Auth/RBAC, Admin AI Vault, Central AI Gateway & Full Observability

### Objectives
Close existing security/auth gaps in `iran-tutor` and build the centralized Admin-controlled AI & Observability backbone (Rules 2 & 3).

### Backend Tasks
1. **Authentication & RBAC:**
   - Implement real role-based access control with roles: `admin`, `teacher`, `student`, `guardian`.
   - Secure ALL `/api/v1/admin/*` endpoints behind strict `admin` (or scoped `teacher`) auth dependencies.
   - Keep a pluggable `SMSProvider` interface (`demo` vs real Iranian SMS gateway via env/admin config) for student OTP login, plus secure password/2FA auth for Admin.
   - Add `users` fields/tables for `role`, `grade_level`, `major`, `is_active`, `plan_id`.

2. **Encrypted AI Provider & Key Vault:**
   - Add Alembic migration & models:
     - `ai_providers` (`id`, `name`, `provider_type` [`openai`, `anthropic`, `gemini`, `openai_compatible`, `local`], `base_url`, `encrypted_api_key`, `is_active`, `capabilities` [`chat`, `vision`, `stt`, `tts`, `embedding`], `created_at`, `updated_at`)
     - `feature_model_routes` (`id`, `feature_key`, `provider_id`, `model_name`, `temperature`, `max_tokens`, `fallback_provider_id`, `fallback_model_name`, `is_active`)
   - Encrypt API keys using Fernet/AES-GCM keyed from `SECRET_KEY` (never return raw keys in API responses; mask as `sk-...xxxx`).
   - Add `POST /api/v1/admin/providers/{id}/test` to verify live connectivity.

3. **Quota & Rate Limiting Engine:**
   - Add `plans` and `user_quotas` tables + Redis sliding-window rate limiter.
   - Enforce daily/monthly token limits, request limits, and per-feature quotas before every AI call.

4. **Central AI Gateway & Full Audit Logging:**
   - Create `backend/app/services/ai_gateway.py` (single entrypoint for ALL LLM, Vision, STT, TTS, and Embedding calls across the entire app).
   - Refactor all direct LLM/Vision/STT calls found in Phase 0 to go through `ai_gateway`.
   - Add `ai_audit_logs` table:
     - `id`, `user_id`, `session_id`, `feature_key`, `skill_id`, `provider_id`, `model_name`, `request_messages_json`, `response_text`, `rag_citations_json`, `rag_hit_count`, `tokens_in`, `tokens_out`, `estimated_cost_usd`, `latency_ms`, `status` (`success` | `error` | `blocked` | `flagged`), `error_message`, `flag_reason`, `created_at`.
   - Auto-flag records when `rag_hit_count == 0` in textbook-strict mode or when a student reports an answer.
   - Add student endpoint `POST /api/v1/feedback/flag` so students can report wrong/unclear AI answers directly into the Admin Flag Queue.

### Frontend Tasks (`/admin`)
1. Protect `/admin` with real Admin Login UI and session handling.
2. Add **AI Providers & Model Routing** management page (CRUD providers, test connection, assign models per feature like `chat`, `solve`, `quiz`, `flashcards`, `vision_ocr`).
3. Add **Users, Roles & Quotas** management page.
4. Add **Glass-Box Observability Center (`/admin/observability`)**:
   - Filterable audit log table (by user, feature, status, date, flagged).
   - Drawer/modal to inspect full prompt, response, attached image/audio, RAG citations, tokens, cost, and latency.
   - Token & cost summary cards per day/feature/user.

### Verification Gate
- Unauthenticated or `student` requests to `/api/v1/admin/*` return `401/403`.
- API keys are never exposed in plaintext in any API response.
- Every AI call creates a complete `ai_audit_logs` row and updates quota usage.
- `pytest` + frontend build pass.

---

## PHASE 2 — Modular Capability Runtime, Skills System, Typed Blocks & Web KB Pipeline

### Objectives
Make Darsyar pluggable for future features (Rule 4) and replace CLI-only book ingestion with an Admin Web KB pipeline.

### Backend Tasks
1. **Capability Registry & Feature Flags:**
   - Add `capabilities` table (`key`, `title_fa`, `description_fa`, `is_enabled`, `allowed_roles_json`, `allowed_plans_json`, `default_route_key`, `config_json`).
   - Seed initial capabilities: `chat`, `solve`, `quiz`, `multimodal`, `flashcards` (disabled until Phase 3).
   - Expose `GET /api/v1/capabilities/me` so the student frontend dynamically shows enabled tools.

2. **Database-Backed Skills System (Inspired by DeepTutor `SKILL.md`):**
   - Add `skills` & `skill_versions` tables (`id`, `slug`, `capability_key`, `subject_scope`, `grade_scope`, `system_prompt`, `pedagogy_rules_md`, `output_schema_json`, `safety_gate_rules`, `version`, `is_active`, `updated_by`).
   - Load active skills dynamically in the Shared Capability Runtime (`backend/app/services/capability_runtime.py`).
   - Admin can edit, test, and rollback skill versions without code deploys.

3. **Typed Learning Blocks Standard:**
   - Define Pydantic schemas (`LearningBlock`) supporting:
     - `text_markdown`, `formula_latex`, `callout_tip`, `citation_ref`, `quiz_item`, `flashcard_item`, `diagram_mermaid`, `diagram_svg`.
   - Ensure the Capability Runtime can emit structured blocks alongside plain streaming text.

4. **Web-Based KB Ingestion & Source Figure Extraction:**
   - Refactor `scripts/ingest_book.py` logic into a reusable service + async background job queue (Redis/worker or FastAPI background runner) tracked by `kb_ingestion_jobs` table (`book_id`, `status`, `total_pages`, `processed_pages`, `error_log`).
   - Extract and store page/embedded images (`source_figures`) so Vision chat can reference actual textbook diagrams.
   - Add Admin endpoints for: upload PDF, trigger/resume/cancel ingestion, re-index single chapter/page, and **Model Benchmark Lab** (compare Vision OCR / Tutor models side-by-side on sample textbook pages).

### Frontend Tasks
1. Dynamic capability navigation in Student UI driven by `/api/v1/capabilities/me`.
2. Shared `LearningBlockRenderer` component (RTL Markdown + KaTeX math + clickable textbook citation badges).
3. Admin **Knowledge Base & Ingestion UI** (upload PDF, live progress bar, chapter/page re-index, figure preview, Model Benchmark Lab).
4. Admin **Skills & Prompts Manager** with version history & rollback.

### Verification Gate
- Admin can toggle a capability off and verify both API (403/disabled) and Student UI hide it immediately.
- Admin can upload a sample PDF via UI, monitor ingestion progress, and inspect/edit extracted pages.
- Admin can edit a Skill prompt and rollback to previous version.

---

## PHASE 3 — First Pluggable Module: Smart Flashcards & Spaced Repetition (SM-2)

### Objectives
Prove the modular Capability Runtime by implementing **Flashcards + Spaced Repetition** end-to-end with Anki export and full Admin visibility.

### Backend Tasks
1. **Database Models & Migrations:**
   - `flashcard_decks` (`id`, `user_id`, `title`, `book_id`, `chapter`, `source_type` [`book`, `chat`, `mistake`, `manual`], `is_public`, `admin_approved`, `created_at`)
   - `flashcards` (`id`, `deck_id`, `front_md`, `back_md`, `hint_md`, `citations_json`, `tags_json`, `created_at`)
   - `flashcard_reviews` (`id`, `card_id`, `user_id`, `ease_factor`, `interval_days`, `repetitions`, `next_review_at`, `last_rating` [1..4], `reviewed_at`)
2. **SM-2 Spaced Repetition Service:**
   - Implement deterministic SM-2 scheduling (`فراموش کردم=1`, `سخت=2`, `خوب=3`, `آسان=4`).
3. **Grounded Flashcard Generation Skill:**
   - Register `flashcards` in Capability Registry & seed `flashcard_generator` Skill.
   - Support generating cards from: (a) Book chapter/page range via RAG, (b) Chat message/session ID, (c) Quiz mistake IDs.
   - All LLM calls go through `ai_gateway` + `ai_audit_logs`.
4. **Endpoints:**
   - Student: CRUD decks/cards, `POST /api/v1/flashcards/generate`, `GET /api/v1/flashcards/due`, `POST /api/v1/flashcards/{id}/review`, `GET /api/v1/flashcards/decks/{id}/export/anki` (generate `.apkg` or Anki-compatible TSV/CSV package).
   - Admin: inspect all user decks/cards, review stats, and moderate/approve shared decks if enabled.

### Frontend Tasks
1. Student `/flashcards` workspace:
   - Deck list with "Due Today" badge & mastery progress bar.
   - "Generate with AI" modal (from Book/Chapter, Chat, or Mistakes).
   - Interactive RTL Flip-Card Study Player with KaTeX math, hint toggle, textbook page citation chip, and 4 SM-2 rating buttons.
   - One-click Anki export button.
2. Add "تبدیل به فلش‌کارت" action button on Student Chat messages.
3. Add Flashcards inspection tab in `/admin`.

### Verification Gate
- Unit tests verify SM-2 interval calculations across ratings 1–4.
- Generating flashcards logs to `ai_audit_logs`, respects quotas, and attaches textbook citations.
- Anki export downloads a valid non-empty file.

---

## PHASE 4 — 3-Layer Inspectable Memory (L1/L2/L3), Hybrid Multi-Grade RAG & Resilient Streaming

### Objectives
Solve `iran-tutor`'s multi-grade Konkoor gap, add DeepTutor-style L1/L2/L3 memory (fully inspectable by Admin), and harden chat streaming.

### Backend Tasks
1. **3-Layer Learner Memory (`learner_memories`):**
   - **L1 (Session Trace):** short-term sliding context & recent tool outputs per session.
   - **L2 (Subject/Chapter Facts):** async post-interaction extraction of mastered/weak subtopics per `book_id`/`chapter`.
   - **L3 (Longitudinal Profile):** synthesized cross-subject student profile (strengths, recurring error patterns, preferred explanation pace).
   - Inject relevant L2/L3 summary into Capability Runtime context automatically.
   - Admin endpoints to **view, edit, or reset** any student's L1/L2/L3 memory entries (`GET/PUT/DELETE /api/v1/admin/users/{id}/memory`).

2. **Hybrid & Multi-Grade RAG (Konkoor Support):**
   - Enhance Qdrant retrieval with metadata filtering across multiple grades (`10`, `11`, `12`) and subjects simultaneously + lightweight **Concept Graph / Cross-Reference Index** (`concept_links` table linking related chapters across grades, e.g., Physics 10th -> 12th) + PageIndex structural lookup.
   - Add **Auto-Mode Router** (`auto` mode in chat) that classifies intent (Explain / Deep Solve / Quiz / Flashcard) using the configured routing model.

3. **Recoverable Streaming & Chat Management:**
   - Implement Redis-backed SSE streaming (`stream_id` cursor) so disconnected clients can resume or fetch completed messages, plus **Stop** and **Regenerate** endpoints.
   - Add full-text chat search and soft-delete **Recycle Bin** (`deleted_at` + restore).

### Frontend Tasks
1. Student chat upgrades: Auto mode option, Stop/Regenerate buttons, recoverable stream indicator, multi-grade Konkoor filter, Chat Search & Recycle Bin.
2. Admin `/admin/users/[id]` **Memory Inspector** tab showing L1/L2/L3 graphs/lists with edit/reset controls.

### Verification Gate
- Multi-grade Konkoor query retrieves and cites chapters from >=2 grade textbooks accurately.
- L2/L3 memory updates after quiz/chat interactions and is visible/editable in `/admin`.
- Stopping/regenerating a stream works cleanly without orphan DB records.

---

## PHASE 5 — Deep Learning Modes: Immersive Reader, Self-Validated Quiz, Mistake Bank, Deep Solve & Mastery Path

### Objectives
Bring the core DeepTutor study loop into Darsyar's student classroom.

### Backend & Frontend Tasks
1. **Immersive Reading (`/study/[bookId]`):**
   - Split-screen RTL UI: Textbook PDF/rendered page image + TOC on one side, grounded AI tutor on the other.
   - Clicking any citation (`فصل ۳، صفحه ۵۴`) jumps the reader directly to that page.
   - Highlight/select region or page context -> "Ask AI", "Summarize", or "Create Flashcards".

2. **Self-Validated Quiz + Automatic Mistake Bank:**
   - Upgrade quiz generation to a 2-stage pipeline: **Generator** -> **Validator Gate** (verifies factual grounding in textbook, LaTeX validity, unambiguous answer key).
   - Add `mistake_bank_items` table: automatically records wrong/skipped quiz questions with error tags & mastery status (`unresolved`, `practiced`, `mastered`).
   - Student `/mistakes` page with targeted re-quiz and 1-click "Send to Flashcards".

3. **Deep Solve (Dual-Loop Step-by-Step Solver):**
   - Decomposes multi-step math/physics/chemistry problems into steps; offers **Hint 1 -> Hint 2 -> Step Reveal -> Full Solution** so students actively solve rather than passively copy.

4. **Mastery Path (`/mastery`):**
   - Chapter & knowledge-point progression tree per book/course; tracks mastery score from quizzes + flashcards + solve sessions and unlocks stages progressively (configurable by Admin).

### Verification Gate
- Quiz Validator catches/fixes malformed or ungrounded test items in unit tests.
- Failing a quiz question automatically creates a `mistake_bank_items` record.
- Citation click in Immersive Reader navigates to the exact printed page.

---

## PHASE 6 — Rich Web Study Surfaces: Learning Notebook, Web Visualize, Living Book & Audio/TTS

### Objectives
Complete the rich web learning suite without adding non-web dependencies.

### Backend & Frontend Tasks
1. **Learning Notebook (`/notebook`):**
   - Block/Markdown workspace backed by `notebooks` & `notebook_blocks` tables.
   - Selection-aware inline AI actions (`ساده‌تر توضیح بده`, `خلاصه کن`, `مثال بزن`, `به فرمول/جدول تبدیل کن`) displaying an inline **Accept / Reject diff** grounded in textbook KB.
   - Export to Markdown / print-ready PDF.

2. **Browser-Native Visualize:**
   - Safe generation & sandboxed rendering of **Mermaid** concept maps, timelines, comparison tables, and sanitized SVG diagrams inside Chat, Notebook, and Living Book.

3. **Living Book (خلاصه تعاملی شب امتحان):**
   - Compiles a chapter's key concepts, callouts, diagrams, mini-quiz, and flashcards into one unified interactive study view (`Typed Learning Blocks`).

4. **Selected-Text TTS & Audio Overview:**
   - Backend endpoint using Admin-configured TTS provider (`ai_gateway`) to read selected explanations or chapter summaries aloud in the browser.

### Verification Gate
- All new features log to `ai_audit_logs`, respect `capabilities` toggles and `user_quotas`, and pass `pytest` + `next build`.
