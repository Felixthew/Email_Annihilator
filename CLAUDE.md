# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal Gmail summarizer running as a FastAPI service on Google Cloud (GCP project `email-endeavor`). It reads recent INBOX mail, summarizes it with Gemini (`gemini-2.5-flash`), and emails an HTML digest to a hardcoded address. There are two triggers: a daily scheduled run, and an on-demand run when an email lands under a custom Gmail trigger label.

## Commands

No tests, linter, or CI exist.

```bash
pip install -e .                                   # installs the package + requirements.txt deps
uvicorn email_annihilator.main:app --port 8080     # run the service
python -m email_annihilator.main                   # one-off 24h summary, no server
python -m email_annihilator.gmail                  # (re)register the Gmail push watch
docker build -t email-annihilator .
```

Code lives in `src/email_annihilator/`; `pyproject.toml` reads dependencies from `requirements.txt`. The Dockerfile does not install the package and still uses `--app-dir src`. Run everything from the repo root. All file paths (`secrets/...`, `prompts/...`) are relative.

Deployment settings (paths, label, topic, recipient, Gemini model, prompt) live in `config.Settings`. `main.py` is the only place that builds `Settings` and the clients (`GmailClient`, `GeminiClient`, `HistoryStore`), per request; everything else receives them as arguments. Only the client modules import vendor SDKs; `summary.py` imports no `google.*`.

## Architecture

**Endpoints (`main.py`):**
- `POST /trigger/scheduled`: the daily run. Calls `run(gmail, {})` with the defaults (last 24h, no addon).
- `POST /trigger/email`: the Pub/Sub push endpoint. It decodes `historyId` from the Pub/Sub envelope, lists Gmail history since the cursor stored in Firestore, parses configs from the newest message under the trigger label, then runs. It always returns 200, even on errors, so Pub/Sub does not retry.
- `POST /trigger/watch`: re-registers the Gmail watch.

**On-demand flow:** `GmailClient.register_watch()` points Gmail push notifications at the Pub/Sub topic `projects/email-endeavor/topics/gmail-push`, filtered to `Settings.trigger_label`. Label-filtered watches are buggy, so it registers an EXCLUDE watch on all system labels first and an INCLUDE watch on the trigger label second. Gmail watches expire, so they must be re-registered periodically.

**History cursor (`store.py`):** Firestore stores the last history ID in `gmail_data/historyID.last_history_id`. `update_historyID` always advances the cursor in `finally`, even when the history fetch fails. The first call only initializes the cursor and does not run a summary.

**Run configs:** the body of the trigger email is lowercased and split on commas. Each `key: value` pair that matches `^[\w\s]*:[\w\s]*$` becomes a config entry. The recognized keys are `hours` (lookback window, default 24) and `addon` (extra text appended to the prompt). Values are not stripped.

**Prompt:** `Settings.prompt_path` selects the file in `prompts/` (currently `v2.txt`). The code appends the current America/New_York time, the addon, and then every email as plain text. The model's markdown output is converted to HTML with `markdown`.

## Gotchas

- `Settings.local_auth`: `False` (the default, for cloud) raises an error when credentials are invalid. `True` opens a browser OAuth flow using `secrets/credentials.json` and rewrites the token.
- Only the `text/plain` part of each email is read (`get_body`). The fetch is capped at 100 messages.

## Secrets

`secrets/` is excluded by both git and Docker. The code expects these files:
- `secrets/token/token.json`: Gmail OAuth token
- `secrets/credentials.json`: OAuth client, used only for the local auth flow
- `secrets/gemini_api_key/gemini_api_key.txt`

The image does not contain them, so in Cloud Run they must be supplied at those paths, presumably as mounted secret volumes given the per-secret subdirectories [unverified].
