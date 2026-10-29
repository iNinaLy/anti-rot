# Deploy Anti-Rot

Repository: https://github.com/iNinaLy/anti-rot

## First deployment (SQLite)

Requires Git, Docker Engine/Desktop and Docker Compose v2. On the server:

```sh
git clone https://github.com/iNinaLy/anti-rot.git
cd anti-rot
cp .env.example .env
```

Generate a secret with `openssl rand -hex 48` (or Python's `secrets.token_urlsafe(48)`) and replace `SECRET_KEY` in `.env`. Set a real `PUSH_CONTACT=mailto:you@example.com`. Keep the container paths and choose a free `PORT`. The default bind address is localhost; use Tailscale Serve below for private HTTPS access. Use `COOKIE_SECURE=true` when accessing over HTTPS.

```sh
docker compose up -d --build --wait
docker compose exec app python -m app.cli create-user
docker compose logs --tail=100 app
```

The account command prompts for email and a hidden password. Public sign-up is disabled. Visit http://localhost:8080 on the server, or use the HTTPS address below. Migrations run automatically. Keep one app worker; background backup coordination is designed for one worker.

The app uses named volumes for database, media and backups. Never run `docker compose down -v` on a deployment with data you want to keep. `.env`, databases, media, backups, local tools and IDE settings are excluded from Git. Do not upload them to GitHub. If moving an existing installation, transfer a backup separately over a private channel and restore it; cloning Git only transfers the application code.

## Private HTTPS through Tailscale

Install Tailscale on the server and your own devices, sign them into your tailnet, and enable HTTPS in the Tailscale admin settings when prompted. On the server:

```sh
tailscale up
tailscale serve --bg http://127.0.0.1:8080
tailscale serve status
```

Use the HTTPS URL printed by Tailscale on your connected devices. This is private tailnet access, not public Funnel hosting. Set `COOKIE_SECURE=true` in `.env` and recreate the app with `docker compose up -d`. HTTPS enables PWA installation and Web Push; on iPhone install to the Home Screen before enabling notifications. Tailscale account setup, device authorization and DNS cannot be configured through this repository alone. See the [official Serve documentation](https://tailscale.com/docs/reference/tailscale-cli/serve).

For an existing public HTTPS reverse proxy, proxy to localhost:8080 instead. Set `BIND_ADDRESS=0.0.0.0` only if you need direct LAN access; plain HTTP LAN addresses do not provide full PWA/notification support.

## Updates and GitHub Container Registry

```sh
git pull
docker compose up -d --build --wait
docker compose logs --tail=100 app
```

GitHub Actions tests the app, checks migrations, builds the image, then publishes `ghcr.io/ininaly/anti-rot:latest` and a commit-SHA tag on pushes to `main`. If the package is private, authenticate on the server with `docker login ghcr.io`. Set `APP_IMAGE=ghcr.io/ininaly/anti-rot:latest` (or a SHA tag) in `.env`, then:

```sh
docker compose pull app
docker compose up -d --no-build --wait
```

The first workflow run and package permissions depend on the repository owner's GitHub settings. GitHub hosts source and container images; it does not itself run this database-backed app.

## Nightly backups and restore

`BACKUPS_ENABLED=true` creates one snapshot per Malaysia date at/after `BACKUP_TIME=03:00`, with catch-up after restarts. `BACKUP_KEEP=7` retains seven daily archives in the backup volume. Requests briefly wait during snapshots so database state and media stay consistent. SQLite uses its backup API; PostgreSQL uses a repeatable-read logical JSON snapshot. Each archive includes media and private Web Push keys. Copy archives off the server; a named volume on the same host is not protection against host failure.

```sh
mkdir -p backups
docker compose cp app:/backups/. ./backups/
```

Archives use `anti-rot-YYYY-MM-DD.tar.gz`. To restore a **trusted nightly archive**, copy it into the backup volume, stop the app, then:

```sh
docker compose stop app
docker compose run --rm --no-deps app python -m app.restore /backups/anti-rot-YYYY-MM-DD.tar.gz --replace
docker compose up -d --wait
```

`--replace` explicitly replaces the SQLite database. PostgreSQL restore requires a fresh empty database already migrated to the matching schema, and refuses to overwrite existing rows. Restoring overlays backed-up media; use fresh volumes when possible to avoid orphaned files. Preserve `.env` securely separately. Do not mix the nightly archive format with the older whole-volume tar commands in README. For a manual immediate backup, use the stopped-app whole-volume backup documented in README. Keep the app stopped if a restore fails and inspect the error before trying again.

## Optional PostgreSQL

For a fresh PostgreSQL deployment, set a random URL-safe `POSTGRES_PASSWORD` in `.env` and use both Compose files consistently:

```sh
docker compose -f docker-compose.yml -f compose.postgres.yml up -d --build --wait
docker compose -f docker-compose.yml -f compose.postgres.yml exec app python -m app.cli create-user
```

The database is on the private Compose network and has its own persistent volume. Changing a URL does not move SQLite data. To transfer data, stop application writes, migrate an empty target to the same schema, and use the portable export/import commands with URLs supplied through environment variables:

```sh
python -m app.transfer export snapshot.json
python -m app.transfer import snapshot.json
```

Export reads `SOURCE_DATABASE_URL`; import reads `TARGET_DATABASE_URL`. Run from `backend` with dependencies/configuration available, or in a one-off app container with both databases accessible. Import refuses any nonempty target. Transfer media and notification keys separately, and switch the app's database only after verifying the target. Snapshot JSON contains private account data and belongs outside Git.

## Optional local AI drafts

```sh
docker compose --profile ai up -d ollama
docker compose exec ollama ollama pull qwen3:0.6b
```

Then open a deck and choose **Generate flashcard drafts from notes or PDF**. The default model is a small local model; change `OLLAMA_MODEL` for a model your server can run. Notes are capped at 16,000 characters; PDFs at 5 MiB/50 pages and require selectable text. Generated cards stay in the browser as editable drafts until explicitly saved. AI can be wrong, so review answers. No paid cloud API is used; model downloads, CPU/RAM, storage and electricity still have costs. Ollama is not exposed on a host port by this Compose setup. [Ollama model information](https://ollama.com/library/qwen3:0.6b).

## Quick verification

```sh
docker compose ps
docker compose logs --tail=100 app
curl -f http://localhost:8080/api/health
```

Sign in, create a deck/card, review a session, and open Exercise, News and Activity history. Enable device notifications on each device and confirm real delivery there. News stays RSS-only; rewards, habits and daily goals are intentionally excluded.
