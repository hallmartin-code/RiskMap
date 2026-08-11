# Deploying to Railway

The app ships as a container. Railway builds the `Dockerfile`, injects `$PORT`,
and serves the Streamlit UI over HTTPS on a generated domain.

---

## 1. Get a Claude API key

1. Open the [Claude Console](https://platform.claude.com/) → **API keys**.
2. **Create key**, scope it to the workspace you want billed, and copy it — the
   value is shown once. It starts with `sk-ant-`.
3. Put some credit on the workspace (**Billing**). Each analysis is one Claude
   request; the reference deck used roughly 3K input / 4.5K output tokens per
   run on `claude-opus-5`.

Do **not** commit the key. It is set as a Railway variable in step 3.

---

## 2. Push the repository

Railway deploys from a Git repository.

```bash
git init
git add -A
git commit -m "Pitch deck one-pager"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

`.gitignore` already excludes `.env`, `input/`, `output/` and `temp/`, so no key
and no deck is ever pushed.

---

## 3. Create the service

1. [railway.com](https://railway.com) → **New Project** → **Deploy from GitHub
   repo** → pick the repository.
2. Railway detects the `Dockerfile` and starts the first build. `railway.json`
   supplies the start command, the `/_stcore/health` health check and the
   restart policy, so there is nothing to configure by hand.
3. Open the service → **Variables** → add:

   | Variable | Value | Required |
   |---|---|---|
   | `ANTHROPIC_API_KEY` | `sk-ant-…` from step 1 | **yes** |
   | `APP_PASSWORD` | a shared password of your choosing | **strongly recommended** |
   | `LLM_MODEL` | `claude-opus-5` (default if unset) | no |
   | `LLM_EFFORT` | `high` (default) — `medium` is cheaper and faster | no |
   | `LLM_MAX_TOKENS` | `16000` (default) | no |
   | `PAGE_SIZE` | `LETTER` (default) or `A4` | no |
   | `SHOW_SOURCE_REFERENCES` | `true` (default) | no |
   | `LOG_LEVEL` | `INFO` (default) | no |

   Do not set `PORT` — Railway provides it.

4. **Settings** → **Networking** → **Generate Domain**. Railway maps the public
   443 port to the container's `$PORT` automatically.

The first build takes a few minutes. Deploy logs should end with
`Uvicorn server started on 0.0.0.0:<PORT>`, and the health check turns green
once `/_stcore/health` returns `ok`.

---

## 4. Verify

1. Open the generated domain. If `APP_PASSWORD` is set you get a sign-in form.
2. The sidebar must show **`ANTHROPIC_API_KEY` detected**. If it shows an error,
   the variable is missing or misspelled — fix it and redeploy.
3. Upload a deck and click **Generate investment one-pager**. Expect roughly
   30–90 seconds on `claude-opus-5` at `high` effort. The page renders inline;
   the PDF and the JSON sidecar are downloadable.

---

## Security notes

**Protect the deployment.** Without `APP_PASSWORD` anyone who finds the URL can
upload decks and spend your API credits. The app displays a warning banner when
it detects a Railway environment with no password set. For more than a handful of
users, put Railway behind your own SSO or an authenticating proxy instead of a
shared password.

**Confidentiality.** Deck text is sent to Anthropic for analysis — that is
inherent to the product. Everything else (parsing, rendering) happens inside your
container. Uploads are written to a per-request temporary directory and deleted
after the response; nothing is persisted, because Railway's filesystem is
ephemeral anyway.

**Key handling.** The key is read from the environment at request time and is
never logged, never written to the JSON sidecar, and never included in the image
(`.env` is in `.dockerignore`). Rotate it in the Claude Console if exposed.

**Logs.** `LOG_LEVEL=INFO` records slide counts, token usage and validation
warnings — not deck contents. `DEBUG` is more verbose; avoid it for confidential
material.

---

## Cost control

- Each generation is one Claude request (two if the compression pass triggers).
- `LLM_EFFORT=medium` measurably reduces token spend; `low` is for latency-
  sensitive, non-critical runs.
- Set a spend limit in the Claude Console; Railway bills compute separately.
- The container idles cheaply — cost is dominated by API calls, not hosting.

---

## Optional: legacy `.ppt` and OCR

Both need system packages. Uncomment the relevant `RUN apt-get` block in the
`Dockerfile` (and `pytesseract` in `requirements.txt` for OCR), then redeploy.
LibreOffice adds roughly 500 MB to the image, so enable it only if you actually
receive binary `.ppt` files. Without them the app rejects those inputs with a
clear message rather than failing silently.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Build fails on `pip install` | Check the build log for the failing wheel. All dependencies have manylinux wheels for Python 3.11; a pinned older version may not |
| Health check never turns green | The start command must bind `$PORT` and `0.0.0.0`. `railway.json` does this; if you overrode the start command, restore it |
| "Application failed to respond" | The container is listening on the wrong port. Do not hard-code `8501` in the start command, and do not set a `PORT` variable yourself |
| `ANTHROPIC_API_KEY is not set` in the UI | The variable is missing on the service, or was added to a different service/environment. Redeploy after adding |
| 401 from Anthropic | Key revoked, or from a workspace with no credit. Create a new key in the Console |
| File upload silently fails | Rare proxy interaction with XSRF. Add `enableXsrfProtection = false` under `[server]` in `.streamlit/config.toml` and redeploy — this weakens CSRF protection, so pair it with `APP_PASSWORD` |
| Upload rejected as too large | Raise `maxUploadSize` in `.streamlit/config.toml` (MB) |
| Analysis times out | Raise `LLM_MAX_TOKENS`, or lower `LLM_EFFORT`. Streamlit holds the connection over a websocket, so there is no HTTP request timeout to tune |
| Session resets unexpectedly | Railway restarted the container (redeploy, crash, or resource limit). Check deploy logs; generation is stateless, so simply retry |

---

## Alternative: build without Docker

Delete or rename the `Dockerfile` and Railway falls back to Nixpacks, which
detects `requirements.txt` and uses the `Procfile` start command. The Dockerfile
path is preferred because it pins Python 3.11 and makes the optional system
packages explicit.

## Running the CLI against the deployed service

The container runs the web app. To generate one-pagers in bulk, run the CLI
locally or in CI with the same environment variables:

```bash
ANTHROPIC_API_KEY=sk-ant-... python cli.py input/deck.pdf
```
