# Anti-Rot

A self-hosted personal app to avoid brainrot through learning, exercise, and a limited news briefing. Flashcards, the exercise checklist, and free RSS news are implemented. Future modules can register without coupling streaks and Today to flashcard tables.

**Deployment handoff:** [DEPLOY.md](DEPLOY.md) has the complete setup for your brother: private HTTPS, updates, nightly backups/restore, optional PostgreSQL and local AI. Repository: https://github.com/iNinaLy/anti-rot. Habits and daily goals are intentionally excluded.

## Product direction

Anki is the scheduling reference: Anti-Rot now uses FSRS-6 via the maintained [py-fsrs implementation](https://github.com/open-spaced-repetition/py-fsrs). The user brought this scheduler upgrade forward from Phase 6. The interface takes its layout and color direction from [Brainscape](https://www.brainscape.com/): navy navigation, cyan accents, white question/answer cards, a deck list, and colored rating controls, while retaining Anti-Rot's identity and four Anki-style ratings.

## What is included

- CLI-only account creation, sign-in, Argon2 password hashing, short-lived JWT access tokens, rotating persistent HttpOnly refresh cookies, logout and database-backed login rate limits. Public sign-up is disabled in both the interface and API.
- Private decks and cards with CRUD, due-today counts, UTF-8 CSV import (`front,back`), and quick sessions of up to 10 due cards by default.
- Organize decks by university subject using the dropdown in New deck / Edit deck. It includes ITT585 (Network Infrastructure Security), ITT610 (Network Security / Security Analysis), ICT652 (Ethical, Social and Professional Issues in ICT), ITT640 (Wireless Networks), and ITT593 (Introduction to Digital Forensics). Choose **+ Add subject…** to save another subject to your private catalog; it remains available even after its decks are deleted. Existing deck subjects are also available. Choose Uncategorized for unassigned decks. Both the deck list and sidebar group by subject; changing a subject preserves cards and review schedules.
- FSRS-6 with Again / Hard / Good / Easy ratings, persistent stability/difficulty and learning state, 1m/10m learning steps, 10m relearning, and default 90% desired retention (`FSRS_DESIRED_RETENTION`, range 0.70–0.99). A new card rated Again returns in 1 minute, Hard in 5m30s, Good in 10 minutes; Easy graduates to a day-based interval. Fuzz is disabled for deterministic scheduling. These choices follow Anki's FSRS approach; Anti-Rot does not reproduce all of Anki's deck options, daily queue rules, or parameter optimizer.
- Installable PWA, cached app shell, offline review sessions and images, and durable, idempotent review sync.
- Front/back images by upload, clipboard paste, camera or gallery. Pillow validates the actual bytes, strips metadata, reduces the longest side to 1600 px, and re-encodes to lossless WebP. Animated GIF/WebP uploads become the first frame. Default limits: 5 MiB/upload and 10 images/card.
- Shared activity completions drive Today and streaks. A session earns one point per reviewed card after **all** its cards sync and the session completes. Days use UTC; a streak stays current if yesterday was the last active day.
- Alembic migrations, backend/frontend tests, Docker packaging, and GitHub Actions to test and publish to GHCR on pushes to `main`.
- Card tags/topic filtering and multiple-choice review, with manual FSRS ratings.
- Optional local AI drafts from pasted notes or text PDFs, reviewed and edited before explicit save. No paid AI API.
- User-defined rewards, an idempotent redemption ledger and point balance, plus record-only activity statistics/heatmap. No habits or daily goals.
- Automatic nightly database/media/notification-key snapshots, restore and portable empty-target database transfer. See DEPLOY.md.

## Run locally

Requires Python 3.12+ and Node.js 22+. From the repository root:

```sh
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell instead: .\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

Create **backend/.env** (the root example uses Docker paths):

```dotenv
SECRET_KEY=replace-this-with-a-long-random-secret-at-least-32-characters
DATABASE_URL=sqlite:///./data/app.db
MEDIA_DIR=./media
STATIC_DIR=../frontend/dist
COOKIE_SECURE=false
```

Generate the secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Then:

```sh
cd backend
mkdir data
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Visit the URL Vite prints (normally http://127.0.0.1:5173). Vite proxies `/api` to port 8000. Interactive API documentation is at http://127.0.0.1:8000/docs. For a single-port production preview, run `npm run build` in `frontend`, then restart the backend and visit http://127.0.0.1:8000. The service worker runs only in production builds.

The optional `.tools/` folder contains ignored development runtimes used during implementation; it is not required, packaged or committed. On this workspace you can substitute `.tools/python/python.exe` for Python and `.tools/node.exe .tools/package/bin/npm-cli.js` for npm (adjust relative paths from subdirectories).

## Flashcard extras and rewards

In a card's editor, add comma-separated **Tags / topics** and optional **Multiple-choice answers** (2–6 lines, including the exact back answer). Use the deck's tag selector to filter cards and the next quick session. On the review screen choose **Recall** or **Multiple choice**. Picking an option reveals feedback; you still choose Again / Hard / Good / Easy. Cards without explicit options can use other batch answers, falling back to recall when fewer than two options exist. Offline batches retain tags and choices.

Open a deck's **Generate flashcard drafts from notes or PDF** panel after enabling local Ollama (DEPLOY.md). Generate, edit and deselect drafts before **Save reviewed drafts**. Generation alone creates no cards. Text PDFs are limited to 5 MiB/50 pages; scanned PDFs need external OCR. Small local models can be inaccurate, so review every answer.

Open **Rewards** to define names/costs, redeem earned points and view redemption/activity history. Points come from shared flashcard/exercise completions; news is never rewarded. Purchases preserve the price/name at redemption, and removing a reward retains history. Transactional balance checks prevent overspending, and duplicate redemption IDs do not spend twice. The heatmap records 365 UTC dates without a daily target or attendance requirement.

## News

Open **News** from the sidebar or **Open news** on Today. Your briefing contains up to **8 stories by default**, adjustable from **5–10**, split across Malaysia, world, and discovery. It uses free public RSS from BERNAMA, Malay Mail, Malaysiakini, BBC, and The Guardian; no paid APIs, AI services, subscriptions, or API keys are used. Publisher access rules still apply to linked articles, and some publishers may require payment for the full story. Headlines/excerpts are shown with source, publication time, and original links; full articles are never scraped or paywalls bypassed.

Briefings use **Malaysia dates** and stay fixed for the day. Mark stories read to reach **“You're caught up.”** Reading earns no points and does not affect activity streaks. There is no infinite scrolling, extra batch, breaking-news notification, or automatic article opening. Subject/news preferences and reading progress are private to your account.

**Briefing preferences** lets you adjust the limit, reduce crime coverage (on by default), and exclude up to 30 words/phrases. Crime filtering uses feed categories and keyword matches and cannot be perfect. Malaysia/world selection favors political/economic keywords and mixes publishers; this is simple curation, not fact-checking or a guarantee of balanced viewpoints. Similar headlines and duplicate URLs are filtered, with a maximum of three stories per publisher. Feed-based geographic categories are approximate.

Preference changes can immediately hide stories or reduce the visible count; they do not refill the briefing. Higher limits and newly available stories apply to the next day's briefing. If all feeds fail or yield no matching stories, an empty briefing may be retried later. Fewer than five stories may be shown when sources/filtering leave too few; the app never invents or pads stories. Feeds are fetched only when needed, cached for 30 minutes, size/time limited, and XML/HTML/link data is validated. Unselected cache entries older than seven days are pruned; stories retained in briefings are preserved. `NEWS_FETCH_ENABLED=false` disables external feed fetching. News requires a connection; only the existing flashcard review flow promises offline sync.

The source feed URLs were checked directly during implementation. News access is for this personal, non-commercial installation; feed availability and publisher terms can change. The browser suite uses clearly labeled synthetic stories in a temporary test database, never in the production app.

## Exercise

Open **Exercise** in the sidebar or its Today card. The interface tracks **Day 1–30**, with a link to your [Nourish Move Love playlist](https://www.youtube.com/playlist?list=PLpa0d6IJAhbgN8nyV8BK-GqN_A8CXgu9c). It links to the playlist rather than assuming each playlist entry is a challenge day; the playlist includes additional/paired workouts. There are no workout descriptions to manage.

- Strength days default to **Tuesday, Friday and Sunday**. Other days show **Walk**.
- Missed workouts never advance the challenge. Completing Day 1 makes Day 2 the next workout, even after a gap. Walks never advance strength days.
- Change **Next challenge day** to set your position manually, select strength weekdays, and pick a reminder time. Day 31 means the challenge is complete. Settings and completions require a connection.
- Reminders default to **8:00 PM Asia/Kuala_Lumpur (UTC+8)**, for both strength and walking days. Enable **Reminders enabled** and click **Enable device notifications** on each device, then allow browser notifications. The enable button also turns on reminders. Disabling device notifications affects that device; unchecking Reminders enabled disables the schedule for all your devices.

Reminders use free Web Push, with no paid service or API key. HTTPS or localhost and a supported browser are required; iPhone/iPad needs the app installed to the Home Screen. The server must remain running and have outbound internet access. Browser/OS settings can delay or block delivery, so this is not an alarm-clock guarantee. A background module task checks every 30 seconds, skips activities already completed, and allows a 30-minute catch-up window after the chosen time. Successful delivery is limited to once per device per Malaysia date. Signing out from the app removes that device's subscription.

`PUSH_KEYS_FILE` stores generated VAPID keys; Compose keeps them at `/data/push-keys.json` in the existing database volume, so existing backup instructions include them. Keep this file private and retain it across restarts. Set `PUSH_CONTACT` to your contact email in `mailto:you@example.com` format. `REMINDERS_ENABLED=false` disables the server reminder worker. Use one app worker. The checkbox writes a shared activity completion, while exercise progress and walking dates follow Malaysia time; the existing combined Today/streak summary still uses UTC days.

Notification timing, deduplication, VAPID key generation and subscription ownership are covered by backend tests; browser setup is tested with a mocked push subscription. Actual delivery to a physical device must be confirmed after enabling it on that device.

## Create your account and stay signed in

Public sign-up is intentionally unavailable. Its interface placeholder is commented out; direct requests to `/api/core/auth/register` return 404, and it is absent from the API documentation. Create your account from a terminal on the server:

```sh
docker compose exec app python -m app.cli create-user
```

The command prompts for your email, password and password confirmation. Password input is hidden and never passed as a command argument. Use at least 10 characters. You can supply `--email your@email.com` to skip the email prompt. Existing accounts remain usable; duplicate email addresses are rejected. For a local Python deployment, run migrations first and execute `python -m app.cli create-user` from `backend` with its environment configured.

Then sign in normally. The browser stores an HttpOnly refresh cookie for **180 days** by default (`REFRESH_TOKEN_DAYS`); each successful refresh renews that period. Short-lived access tokens are renewed automatically, including after a browser restart, and refreshes are serialized across tabs where Web Locks are available. Signing out revokes the cookie. Clearing browser cookies, private browsing, or letting the renewal period expire requires signing in again. Use `COOKIE_SECURE=true` for HTTPS deployments; localhost HTTP needs `false`.

## Run tests

```sh
cd backend
python -m pytest
# With SECRET_KEY / DATABASE_URL configured:
python -m alembic upgrade head
python -m alembic check
cd ../frontend
npm test
npm run build
```

Backend tests use isolated temporary databases/media directories and cover authentication, refresh rotation, rate limiting, ownership, CRUD, CSV validation, known SM-2 cases, review idempotency/conflicts, activity streaks and image validation/EXIF/ownership/deduplication/cleanup. Vitest covers persistence, account isolation, sync ordering, retries and conflict retention.

To run the same backend suite against PostgreSQL, set `TEST_DATABASE_URL` to a **dedicated, empty test database**. Tests create and drop the application's tables there. CI runs both SQLite and PostgreSQL suites. For a production browser test, first build the frontend, run `npx playwright install chromium`, then `npm run test:e2e` from `frontend`. Python must be on PATH; the test starts a temporary backend and checks image upload, offline reload/review, credential expiry, reconnect/sync and mobile layout.

Implementation verification: 53 backend tests passed on SQLite and PostgreSQL 16, including CLI provisioning, disabled public registration, FSRS reference cases, learning/relearning transitions, and historical review migration; 6 Vitest tests passed. All four production Playwright flows passed, including cookie-only session restoration, simultaneous browser tabs, sign-out, and offline reviews. TypeScript/Vite build, Alembic upgrade/downgrade/schema-drift checks on both databases, npm dependency audit, Docker build, and Compose health/API/frontend smoke checks passed. The GitHub workflow runs these checks before publishing the deployment image. Deployment handoff is documented in DEPLOY.md. Browser screenshots of the dashboard and review screen at desktop/mobile sizes are saved under ignored `artifacts/` when the browser test runs.

## Offline use and installation

Use HTTPS, or localhost for development. Browsers require a secure context for service workers, installation, camera/clipboard capabilities and `crypto.randomUUID`. A plain HTTP LAN IP can serve the website but does not provide a reliable PWA environment.

1. Open the production app online and sign in. Install it using the browser's Install app / Add to Home Screen action.
2. Create a deck and cards. Save a card before attaching images; edit it to add images or paste into the appropriate side.
3. Start a quick session online. The server selects due cards, and the app caches that batch and all its images before showing the session as offline-ready.
4. You can disconnect, reload, reveal answers and rate that saved session. Keep the browser's site storage; private data is in IndexedDB on this device.
5. Reconnect and open the app. It syncs immediately, on reconnect, and every minute while open. You can also click the sync indicator. A fresh access token is requested using the refresh cookie if needed.

Deck/card edits, imports and starting a new session require a connection. Sync runs while the app is open; background browser execution is not assumed. The server checks card versions, so conflicting reviews from another device pause sync visibly. Pending reviews remain stored until retried or explicitly discarded. A completed offline session updates the streak only after sync, using its server completion day. Refresh expiry opens a reconnect dialog for the same account while keeping pending reviews. Signing out clears private caches and warns before discarding unsynced reviews; sign out while online so the refresh cookie can be revoked.

Images have no public URL. Authenticated fetches become user-keyed IndexedDB blobs for offline use; the service worker caches only public app-shell assets. Anyone with access to the unlocked browser profile can read its offline data. Use a dedicated OS/browser profile on shared computers.

## Deploy on a homelab

### Prerequisites and first start

Install Docker Engine/Desktop with Docker Compose v2 and Git. Start Docker, create your own GitHub repository, push this project, and clone that repository onto the server:

```sh
git clone https://github.com/YOUR-ACCOUNT/YOUR-REPO.git
cd YOUR-REPO
cp .env.example .env
```

On PowerShell use `Copy-Item .env.example .env`. Edit `.env`: generate a random `SECRET_KEY`, choose `PORT` (default 8080), and set `COOKIE_SECURE=true` when accessed through HTTPS. Keep the container paths for SQLite, media and static files. `APP_IMAGE` is optional and defaults to `daymark:local`. All other settings and defaults are listed in `.env.example`.

```sh
docker compose up -d --build
docker compose ps
docker compose logs -f app
```

Run `docker compose exec app python -m app.cli create-user` to create your account, then open `http://SERVER:8080` (or your HTTPS reverse-proxy address) and sign in. One container serves the frontend and API. Migrations run on startup, and the healthcheck probes `/api/health`. The container runs as a non-root user. Compose mounts separate named volumes for the database and media.

For HTTPS, put your existing reverse proxy in front of port 8080 and set `COOKIE_SECURE=true`. Public registration is disabled; accounts require local CLI access. Run one app worker for this SQLite deployment. Login limits use the directly connected IP and normalized email; forwarded headers are not trusted. A reverse proxy's shared IP limit may need adjustment with `LOGIN_ATTEMPTS`.

### Update

Back up both volumes first, then:

```sh
git pull
docker compose up -d --build
docker compose logs --tail=100 app
```

For GHCR images, GitHub Actions publishes `ghcr.io/your-account/your-repo:latest` and a commit SHA tag after tests pass. Set `APP_IMAGE` in `.env` to that image, authenticate with `docker login ghcr.io` if the package is private, then:

```sh
docker compose pull app
docker compose up -d --no-build
```

Use a SHA tag for reproducible deployment. The workflow requires Actions enabled and package write permission; it uses the repository's `GITHUB_TOKEN`, so no personal token belongs in the source. This project has not been pushed or published by the implementation agent.

### Back up and restore BOTH volumes

A database without its media leaves broken image cards. For a consistent small homelab backup, stop the app during the copy. These commands work in POSIX shells and PowerShell when run as separate lines from the repository directory:

```sh
mkdir backups
docker compose stop app
docker compose run --rm --no-deps --user root --cap-add DAC_OVERRIDE -v ./backups:/backup app python -c "import tarfile; t=tarfile.open('/backup/daymark-backup.tar.gz','w:gz'); t.add('/data',arcname='data'); t.add('/media',arcname='media'); t.close()"
docker compose start app
```

Copy the backup off the host and save `.env` securely separately. The tarball contains private learning data, notification keys, and both volumes. The temporary backup helper needs `DAC_OVERRIDE` to read the mode-0600 notification key; the running app continues to drop all capabilities. Check the backup command succeeded before restarting. To restore a **trusted** backup, stop the app and restore into empty volumes (restoring over newer files can leave orphaned media):

```sh
docker compose stop app
docker compose run --rm --no-deps --user root --cap-add DAC_OVERRIDE --cap-add CHOWN --cap-add FOWNER -v ./backups:/backup app python -c "import tarfile,os; t=tarfile.open('/backup/daymark-backup.tar.gz'); t.extractall('/',filter='data'); t.close(); [os.chown(os.path.join(root,n),10001,10001) for base in ('/data','/media') for root,dirs,files in os.walk(base) for n in dirs+files]; [os.chown(p,10001,10001) for p in ('/data','/media')]"
docker compose start app
```

Do not use `docker compose down -v` unless you intend to delete your data. Keep the app stopped if a backup or restore fails and inspect its error. For running SQLite snapshots, use SQLite's backup API rather than copying an active database file; the automatic nightly backup module now coordinates snapshots with app requests. Nightly archive restore instructions are in DEPLOY.md.

## Architecture and extension points

```text
backend/app/
  config.py, db.py, registry.py, media.py, main.py
  modules/core/        users, auth, activity completions, Today
  modules/flashcards/  decks, cards, sessions, reviews, images, FSRS
  modules/exercise/    challenge progress, walks, schedules, Web Push
  modules/news/        RSS feeds, daily briefings, preferences, reading progress
backend/migrations/   initial schema and FSRS history migration
frontend/src/
  modules/core/        auth, IndexedDB, activity registry, Today
  modules/flashcards/  activity card, images, offline synchronization
  modules/exercise/    exercise checklist, settings, device notifications
  modules/news/        finite briefing and filtering controls
  App.tsx              navigation and flashcard screens
```

UUID columns use SQLAlchemy's portable `Uuid`; timestamps are UTC, with a portable type adapter restoring timezone information from drivers that return naive datetimes. Database configuration uses a SQLAlchemy URL. To use PostgreSQL, provide a database and `postgresql+psycopg://...` URL, run Alembic migrations, and migrate existing data separately. Changing the URL does not copy SQLite data. Media stays on its separate volume.

`Scheduler.next_state(state, rating, now)` is the scheduling boundary; the active FSRS adapter is in `fsrs_scheduler.py`. `sm2.py` remains as the legacy implementation with regression tests. Migration `0002` adds memory fields and replays historical ratings in chronological order using the pinned FSRS engine. It preserves existing due dates, intervals, counters, versions and logs; new submissions use FSRS and logs record `fsrs6` (historical records are marked `sm2`). Changing desired retention affects subsequent reviews rather than bulk-rescheduling existing cards. Default FSRS parameters are used; per-user optimization is not implemented.

Review history is append-only during review submission; deleting a card/deck intentionally deletes its associated review history. `MediaStore.save(user_id, bytes) -> hash`, `open(hash)`, and `delete(hash)` isolate local content-hash storage. Swap the dependency for S3-compatible storage later. Files are removed when the last live image reference is deleted.

### How to add a new module

1. Add `backend/app/modules/<name>/` with `models.py`, `schemas.py`, `router.py`, `service.py` and `__init__.py`. Export `module = Module(name, router, activity_provider)`; package discovery registers routers/providers at startup. Add an Alembic migration for its tables.
2. Write completed activities to `core.ActivityCompletion` with a user, unique activity type/reference, UTC timestamp and points. Return that module's activity summary from its provider. Shared Today/streak queries must continue reading only activity completions.
3. Add `frontend/src/modules/<name>/register.tsx` exporting an `ActivityModule` and Today component. Vite discovers registrations automatically. Add the module's screens and navigation as its feature requires; other activity modules need no changes.
4. Add ownership, completion and module-specific behavior tests.

Phase 2's free news module and the simplified Phase 3 exercise module are implemented. The manual-task module was removed from the plan. The requested flashcard extras, rewards and operations are implemented; habits and daily goals are excluded. See DEPLOY.md for host-specific Tailscale setup and model installation.

Implementation references: [FastAPI JWT guidance](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) and [SQLAlchemy portable types](https://docs.sqlalchemy.org/en/20/core/type_basics.html).
