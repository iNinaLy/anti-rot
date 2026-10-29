Build Phase 1 of a self-hosted spaced-repetition web app, designed so
it can later grow into Anti-Rot, a personal app to avoid brainrot through
flashcards, exercise, and a limited daily news briefing. Phase 1 is
flashcards only, but the architecture must not assume flashcards are the
only feature.

PRODUCT REFERENCES (user direction)
- Private, single-user installation: public sign-up is disabled in
  the UI and API. Provision accounts through the local CLI; retain
  sign-in and a persistent, rolling refresh cookie (180-day default).
- Scheduling algorithm: Anki-style FSRS-6, implemented with py-fsrs.
  The user explicitly brought the scheduler upgrade forward. Use
  Again / Hard / Good / Easy, 1m and 10m learning steps, a 10m
  relearning step, and 90% desired retention by default. Preserve
  review history and existing due dates when migrating from SM-2.
- Frontend layout, coloring, and visual design: Brainscape-inspired
  navy navigation, cyan accents, white question/answer cards, deck
  lists, and colored rating controls. Retain Anti-Rot's identity and
  the four FSRS ratings.

STACK
- Backend: Python, FastAPI, SQLAlchemy 2.x, Alembic migrations
- Database: SQLite (file path from env var), no SQLite-specific hacks
  so Postgres is a drop-in later
- Frontend: React + Vite + TypeScript, built as an installable PWA
  (manifest + service worker)
- Packaging: Dockerfile and docker-compose.yml, data volume mounted
  for the SQLite file
- Tests: pytest for backend, Vitest for frontend
- Image processing: Pillow (validation, resize, re-encode)

ARCHITECTURE (the important part)
- Modular backend: app/modules/<name>/ each with its own models,
  schemas, router, and service. Phase 1 has two modules:
  `core` (users, auth, shared "daily activity" system) and
  `flashcards` (decks, cards, reviews).
- Module registry: modules register themselves with the app at startup
  (routers, and an "activity provider"). Adding a module later must not
  require editing other modules.
- Shared activity system in `core`: an `activity_completions` table
  (user_id, activity_type, activity_ref, completed_at, points). The
  flashcards module writes a completion when a review session is
  finished. Streaks and the "Today" summary read only from this table,
  never from flashcard tables directly.
- Scheduler isolated behind an interface: `Scheduler.next_state(card_state,
  rating, now) -> card_state`. FSRS now implements this interface;
  the legacy SM-2 implementation remains for historical tests.
- Frontend mirrors this: src/modules/flashcards/, src/modules/core/,
  and a shared "Today" page that renders a card per registered activity.
- Media storage behind an interface: `MediaStore.save(user_id, bytes)
  -> file_hash` and `MediaStore.open(file_hash)`. Phase 1 uses the
  local filesystem under MEDIA_DIR (a Docker volume, separate from
  the database volume). Files are named by content hash, so
  duplicates are stored once. S3-compatible storage can replace it
  later without touching routes.

DATA MODEL (flashcards)
- users(id, email, password_hash, created_at)
- decks(id, user_id, name, description, created_at)
- cards(id, deck_id, front, back, created_at)
- card_states(card_id, due_at, interval_days, ease, reps, lapses,
  last_reviewed_at)
- reviews(id, card_id, rating, reviewed_at, prev_interval, new_interval)
  (append-only log, useful for stats and a future FSRS migration)
- All IDs UUIDs; all timestamps UTC.

FEATURES (Phase 1)
1. Auth: CLI account creation and web login; public sign-up disabled.
   Passwords hashed with Argon2, short-lived
   access token plus refresh token, rate limiting on login.
2. Decks and cards: full CRUD. Every query is scoped to the current
   user; add tests proving one user cannot read or edit another's data.
3. Review flow: GET due cards for a deck, show front, reveal back,
   rate Again / Hard / Good / Easy, FSRS updates the card state.
4. Quick session mode: review a limited batch (default 10 cards).
5. CSV import: front,back columns into a chosen deck, with validation
   and a summary of imported/skipped rows.
6. Home screen: decks with due-today counts.
7. Streak: consecutive days with at least one completed review session,
   computed from activity_completions.
8. PWA: installable, app shell cached; due cards and queued reviews
   work offline and sync when back online (idempotent review submit
   using a client-generated review id).
9. Card images:
   - Attach images to the front and/or back of a card by file
     upload, clipboard paste, or phone camera/gallery.
   - Upload limits from env vars (default 5 MB per image, 10 images
     per card). Allowed types: JPEG, PNG, WebP, GIF. SVG is NOT
     allowed.
   - Validate by decoding with Pillow, not by trusting the file
     extension or Content-Type header. Strip EXIF metadata, resize
     to a maximum of 1600 px on the longest side, and re-encode.
   - Serve images only through an authenticated endpoint that checks
     the requesting user owns the card. No public media URLs. Send
     `X-Content-Type-Options: nosniff`.
   - Review screen shows images with the text, and the PWA caches
     images for due cards so offline reviews still show them.
   - Deleting a card or image removes the file when no other card
     references its hash.
   - CSV import stays text-only in Phase 1.

ROADMAP (build in this order, one phase at a time)
Phase 1 is implemented. The user explicitly brought the simplified
Phase 3 exercise module forward; it is now implemented. Phase 2 news
is also implemented. The user authorized the remaining phases except habits and daily goals. Unscheduled .apkg import and sharing remain outside this request.

Phase 1 (now): flashcards, auth, FSRS (brought forward), CSV import, quick session,
  streak, PWA offline sync, Docker, GitHub deployment setup.
Phase 2: `news` module (implemented). A free daily briefing using public RSS feeds;
  replaces the previously planned manual-task module.
  - Malaysia: politics, economics, policy, and interesting local news.
  - World: major developments, international politics, and economics.
  - Discovery: science, technology, culture, and other interesting finds.
  - Show 5–10 stories TOTAL per day across these categories, with an
    explicit "You're caught up" ending. No infinite scrolling,
    breaking-news notifications, or points for consuming more news.
  - Reduce crime coverage by default using adjustable category/keyword
    exclusions; acknowledge that filtering cannot be perfect.
  - Use multiple publishers, especially for political coverage;
    deduplicate repeated stories where practical.
  - Show source, publication time, available RSS excerpt, and the
    original article link. Prioritize accessible sources; some linked
    articles may have publisher paywalls. Do not bypass paywalls.
  - Free RSS only: no paid news APIs, AI services, or subscriptions.
    Existing hosting and internet costs still apply. Do not add a
    source that requires payment; verify feed availability before use.
  - Register backend/frontend news modules and a Today briefing card.
    Keep reading progress separate from rewarded activity completions.
  - Test feed parsing/failures, deduplication, daily story limits,
    crime exclusions, source attribution, and private reading progress.
Phase 3: `exercise` module (implemented early at the user's request).
  - Day 1–30 checklist linked to the supplied Nourish Move Love
    YouTube playlist; no extra workout descriptions.
  - Missing a scheduled workout never advances the current day;
    completing it advances exactly one day. The user can set the day.
  - Strength defaults to Tuesday, Friday and Sunday. All other days
    are walks; walking completion never advances the challenge.
  - Editable weekdays and reminder time. Latest preference: 8:00 PM
    Malaysia time (Asia/Kuala_Lumpur), superseding the earlier AM choice.
  - Free, opt-in Web Push for strength/walking reminders, persistent
    keys, per-device subscriptions, and no duplicate successful send
    for the same local day. Requires permission, supported browser,
    HTTPS/localhost, and a running server; actual delivery is best effort.
  - Shared activity completion records, ownership/version checks,
    idempotent completion, migration, and backend/browser tests.
Phase 4: habits and daily goals EXCLUDED at the user's request.
  Record-only activity statistics/heatmap are included; existing streaks
  and exercise notifications remain. No habit tracker or goal is added.
Phase 5: implemented. Multiple-choice review, tags/topic filters,
  optional local Ollama drafts from notes/text PDFs (explicit review/save),
  and user-defined rewards with a transactional redemption ledger.
Phase 6: scheduler upgrade brought forward and implemented at the
  user's request: FSRS behind Scheduler, migrated using the reviews
  log. Future parameter optimization and scheduler settings UI may
  be considered separately.
Phase 7: implemented/configured. Nightly SQLite/logical PostgreSQL
  backups include media and notification keys; retention and restore
  tools, optional PostgreSQL Compose deployment, portable data transfer,
  GitHub CI/GHCR packaging, and Tailscale HTTPS deployment instructions.
  Tailnet account/device authorization is performed by the server owner.
Unscheduled: .apkg import, multi-user sharing.

The news module is implemented. The manual-task module
has been removed from the plan; the simplified exercise module is implemented.

DEPLOYMENT (GitHub-ready)
- Repo must be ready to push to GitHub: .gitignore covering .env,
  *.db, node_modules, __pycache__, and build output. Never commit
  secrets or database files.
- .env.example listing every variable (SECRET_KEY, DATABASE_URL,
  ACCESS_TOKEN_MINUTES, etc.) with safe placeholder values.
- docker-compose.yml that runs the app with one command, reading
  from .env, with the SQLite file on a named volume and a
  healthcheck.
- GitHub Actions workflow (.github/workflows/docker.yml): on push to
  main, run tests, then build the Docker image and publish it to
  GitHub Container Registry (ghcr.io).
- README section "Deploy on a homelab" written for someone who didn't
  build the app: prerequisites (Docker + Compose), clone, copy
  .env.example to .env and fill it in, `docker compose up -d`,
  how to update (`git pull` + rebuild, or pull the new image),
  how to back up the SQLite volume, and how to view logs.
- docker-compose.yml mounts two volumes: one for the database, one
  for MEDIA_DIR. The README backup section must cover both, since
  a database backup without the images leaves broken cards.

QUALITY REQUIREMENTS
- Type hints and Pydantic schemas on every endpoint.
- Alembic migration for the initial schema.
- Config via environment variables with a .env.example.
- Unit tests for the SM-2 scheduler (known input/output cases),
  auth, ownership checks, and CSV import.
- FSRS known outputs, reference-engine parity, learning/relearning,
  retention settings, and historical migration preservation tests.
- README: how to run locally, run with Docker, run tests, a short
  "how to add a new module" section, and the homelab deploy section.
- Tests for image upload: rejects oversized files, rejects a
  renamed non-image file, rejects SVG, strips EXIF, and blocks
  another user from fetching your image.

DELIVERABLES
- Working repo with the structure above, `docker compose up` serving
  the app on one port, and all tests passing.
- Work in small steps: scaffold, backend core, flashcards module,
  frontend, PWA/offline, Docker, GitHub Actions and deploy docs.
  Summarize what was done after each.
