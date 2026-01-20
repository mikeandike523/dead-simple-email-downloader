# dead-simple-email-downloader

Download your emails into a large folder that is easy to examine at a glance.
As much information is preserved as possible, leading to archives that are round-trip safe in usual conditions.

At this time, complex compliance and retention features are not implemented.
This is simply an email download automation app, comparable to clicking the appropriate buttons in the outlook.com web app manually.

## Birds-eye view

This repo is two things that work together:

- A Next.js app that exposes `/api/*` endpoints for Outlook OAuth, indexing, and downloading. It talks to Microsoft Graph and persists tokens in MySQL.
- A Python CLI (`cli.py`) that drives those endpoints and writes a local archive to `.dsed/`.

Flow at a glance:

1. Start the Next.js server (`pnpm run dev` or `pnpm start`) and the MySQL Docker stack.
2. Use the CLI to login and create a local JWT (`.dsed/jwt.json`).
3. Index Outlook folders and message metadata into `.dsed/index`.
4. Download messages into `.dsed/caches`.

## Prerequisites

- Node.js + pnpm (Next.js frontend and API routes).
- Python 3 (CLI).
- Docker (MySQL + phpMyAdmin). The app expects the DB to be running.
- Azure app credentials and OAuth redirect URL configured in `.env`.

Notes for this environment:

- Runtimes and package managers are on the Windows host. `pnpm` and `node` run from there.
- For Python, `bash __inenv ...` is recommended to get a reliable interpreter in WSL.

## Setup

1. Review environment files:
   - `.env` in the repo root (Azure + MySQL + JWT).
   - `database/.env` (MySQL + phpMyAdmin for Docker).
2. Start the database:
   ```bash
   docker compose -f database/docker-compose.yml up -d
   ```
3. Install Node dependencies:
   ```bash
   pnpm install
   ```
4. Install Python dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
5. Start the Next.js server (required for all CLI actions):
   ```bash
   pnpm run dev
   # or
   pnpm start
   ```

If the Next.js server is not running, the CLI will fail because it calls `http://localhost:3000/api/...`.

## CLI usage

All commands are under `cli.py outlook ...`.

### Login and session

- `python cli.py outlook login`
  - Opens the Microsoft OAuth flow in your browser.
  - Saves a JWT to `.dsed/jwt.json` for subsequent CLI calls.
- `python cli.py outlook logout`
  - Revokes the server session (if possible) and deletes `.dsed/jwt.json`.
- `python cli.py outlook me`
  - Prints the current user info and token metadata.

### Folder discovery and counts

- `python cli.py outlook folders`
  - Fetches the Outlook folder tree and saves debug output to `.dsed/debug/folders.json`.
- `python cli.py outlook total-emails`
  - Prints per-folder counts and a total across all folders.

### Indexing (required before downloading)

Indexing builds the local `.dsed/index` artifacts that the download step relies on.

- `python cli.py outlook index`
  - Fetches folder structure, message IDs, top-level metadata, and conversation ordering.
- `python cli.py outlook index --reset`
  - Deletes `.dsed/index` and starts fresh.

### Downloading

- `python cli.py outlook download`
  - Downloads all messages based on `.dsed/index`.
  - Output goes to `.dsed/caches/<folder-id>/<conversation-id>/<message-id>/`.
  - If indexing has not been run, this command fails and tells you to run indexing first.
- `python cli.py outlook download --reset`
  - Deletes `.dsed/caches` and exits (no download).

### Safe delete

Safely find and delete messages by exact sender/subject or regex subject.

- `python cli.py outlook safe-delete --exact-sender "user@example.com" --exact-subject "Subject"`
- `python cli.py outlook safe-delete --prompt` (interactive)
- `python cli.py outlook safe-delete --regex --exact-subject "Subject.*"`
- `python cli.py outlook safe-delete --report` (preview only)
- `python cli.py outlook safe-delete --soft` (move to trash instead of hard delete)
- `python cli.py outlook safe-delete -y` (skip confirmation)

## Local data layout

- `.dsed/jwt.json` - CLI JWT after login.
- `.dsed/index/` - index artifacts (folders, message ids, metadata, conversations).
- `.dsed/caches/` - downloaded messages, attachments, and body content.
- `.dsed/debug/` - diagnostic output (folder listings, errors).
- `database/db_data/` - MySQL and phpMyAdmin volumes.

## Common workflows

Download everything:

```bash
pnpm run dev
docker compose -f database/docker-compose.yml up -d
python cli.py outlook login
python cli.py outlook index
python cli.py outlook download
```

Preview and then delete messages:

```bash
python cli.py outlook safe-delete --exact-sender "user@example.com" --exact-subject "Subject" --report
python cli.py outlook safe-delete --exact-sender "user@example.com" --exact-subject "Subject"
```

## Troubleshooting

- If any CLI command says "JWT not found", run `python cli.py outlook login`.
- If API calls fail, confirm `pnpm run dev` or `pnpm start` is running.
- If login or API calls fail, confirm Docker is running and the database is up.
- If downloads fail after indexing, try `python cli.py outlook index --reset`.

## Tests

No automated tests or mock data are currently available for this project.
