# Clarisync In-House LLM Platform

A self-hosted AI chat platform for Clarisync employees. It runs on company hardware so confidential work stays inside Clarisync's infrastructure instead of going to public AI tools.

**This repository is the dev stack.** LibreChat on port 3081, admin panel on `127.0.0.1:3001`, original container names, MongoDB `clarisync-mongo` on `127.0.0.1:27017`, image `librechat`. It uses the shared native services (gateway, Docling, OCR adapter), which run from the prod repo (`self-hosted-llm`); see sections 5.6 and 10. Do not set `COMPOSE_PROJECT_NAME` in this repo's `.env`.

| Layer | Component |
|---|---|
| Interface | LibreChat (patched, built locally) |
| Routing | Custom FastAPI gateway |
| Model serving | Ollama |
| Document reading | Docling (CPU only) behind two small FastAPI services |
| Data | MongoDB (chats, users), Postgres/pgvector (LibreChat's native file-upload feature only) |
| Sign-in | Microsoft Entra ID over SAML, handled by LibreChat's built-in support (section 11) |

## Contents

1. [Scope and status](#1-scope-and-status)
2. [Architecture](#2-architecture)
3. [Repository layout](#3-repository-layout)
4. [Prerequisites](#4-prerequisites)
5. [Setup from a fresh clone](#5-setup-from-a-fresh-clone)
6. [Ports](#6-ports)
7. [Configuration reference](#7-configuration-reference)
8. [Changes made to upstream LibreChat](#8-changes-made-to-upstream-librechat)
9. [Rebuilding and branding](#9-rebuilding-and-branding)
10. [Daily operation](#10-daily-operation)
11. [Sign-in (SAML)](#11-sign-in-saml)
12. [Security notes](#12-security-notes)
13. [Known issues and limitations](#13-known-issues-and-limitations)
14. [Troubleshooting](#14-troubleshooting)
15. [Testing](#15-testing)
16. [Maintainers](#16-maintainers)

---

## 1. Scope and status

**Phase 1 (pilot):** 8 weeks, 12 to 15 users, 4 to 5 departments, on one shared machine (Intel i7-14700K, 64 GB RAM, NVIDIA RTX 4070 Ti with 12 GB VRAM). The 12 GB VRAM limit is a hard ceiling and there is no failover GPU.

**Models**

| Role | Ollama name | Base model | Context |
|---|---|---|---|
| Text (default) | `quick-qwen3-8b` | `qwen3:8b` | 32768, KV cache quantised to q8_0 |
| Vision | `quick-ministral3-8b` | `ministral-3:8b` | 8192 |

Only one model is resident in VRAM at a time. The text model is the default. The gateway swaps the vision model in when an image is attached and swaps back afterwards. Users see a single model, "Quick".

**In scope for Phase 1:** chat, document attachments (PDF, DOCX, XLSX, PPTX), image attachments, thumbs up/down feedback, Clarisync branding.

**Out of scope for Phase 1**

- General and Deep model tiers. Their weights (about 13 GB and 19.5 GB) do not fit in 12 GB of VRAM.
- Retrieval-augmented knowledge base (Phase 2).
- Coding-assistant use cases. These are routed to Claude Enterprise or AWS Bedrock outside this stack.

**Status**

- Gateway, Docling pipeline and OCR adapter: built and verified.
- Branding: applied and baked into the client build (section 9).
- SAML sign-in: working end-to-end against Microsoft Entra ID on both stacks. Local email login is off except a break-glass admin. Still served on `localhost` ports; the move to `https://192.168.90.22` is pending HTTPS setup (section 11).
- Two stacks run side by side on the shared machine: prod (the pilot, port 3080) and dev (3081). They share the native services (gateway, Docling, OCR adapter) and the GPU (section 10).
- Network exposure: gateway, OCR adapter, Docling, Ollama and both MongoDB instances are bound to `127.0.0.1` (section 6). Open items: firewall scoping for RDP/AnyDesk/Zabbix, and HTTPS (section 12).
- Pilot success is measured: response latency, GPU pressure, and negative feedback classified by cause (capability, performance, product).

---

## 2. Architecture

```
Browser
  |
  v
LibreChat  (Docker, :3080)          admin panel (Docker, :3000)
  |   |
  |   +-- DOCX / XLSX / PPTX uploads --> OCR adapter (:8002) --+
  |                                                            |
  +-- chat requests (OpenAI format)                            v
        |                                             Docling service (:8001, localhost only)
        v                                                      ^
   Gateway (FastAPI, :8000) --- PDF attachments --------------+
        |
        v
   Ollama (:11434)  ->  quick-qwen3-8b (text)  |  quick-ministral3-8b (vision)

LibreChat data:  MongoDB container `clarisync-mongo` (:27017)
File-upload vectors:  vectordb (Postgres/pgvector) + rag_api  (LibreChat's native feature)
Search index:  chat-meilisearch
```

**Gateway** (`gateway/`): exposes `POST /v1/chat/completions` in OpenAI format. LibreChat treats it as a custom endpoint named "Clarisync Gateway".

- Routing: an image in the last message goes to the vision model, everything else to the text model. The model picked in the LibreChat UI is ignored.
- Swap orchestration: explicitly unloads the other model before loading a new one, so the 12 GB card never holds both.
- Text calls force `think: false`.
- PDF attachments arrive as base64 file parts on every turn. The gateway converts each through Docling and places the Markdown in the same message as the user's text.
- Size guard: refuses prompts that exceed the model's context window, using Ollama's exact token count for large prompts.
- Errors the user can act on (unreadable file, over the page limit, chat too long) return HTTP 400 with an OpenAI-shaped body. Ollama or Docling outages return 503 or 504.
- Streaming is simulated: the full answer is generated, then sent as one chunk.
- Every request appends a line to `gateway/gateway_metrics.jsonl` (swap type, Ollama's own load and total durations, document timings).
- `GET /health` reports Ollama and Docling reachability.

**Docling service** (`docling_service/`): CPU only, warm-started, in-memory cache keyed by file hash (32 documents), one conversion at a time, 25 MB and 30 page limits. Bound to `127.0.0.1` because it has no authentication.

**OCR adapter** (`ocr_adapter/`): imitates the small part of the Mistral OCR API that LibreChat's built-in `ocr:` feature calls, and forwards the work to Docling. Nothing leaves the machine.

**Which path handles which file**

| File type | Path |
|---|---|
| Text | LibreChat to gateway to Ollama |
| Image | LibreChat to gateway, routed to the vision model |
| PDF | LibreChat sends a file part to the gateway, gateway calls Docling |
| DOCX, XLSX, PPTX | LibreChat `ocr:` route to the OCR adapter to Docling; the extracted text goes into the prompt |
| Other types | Untested. LibreChat may handle or ignore them (section 13) |

---

## 3. Repository layout

```
.
|-- README.md
|-- .gitignore
|-- LibreChat/                      Patched LibreChat source and deployment config
|   |-- api/  client/  packages/    Upstream source (patched files listed in section 8)
|   |-- branding/                   Reference copy of the branding files (live copies are in client/, baked into the build)
|   |-- docker-compose.yml          Upstream compose file (bundled MongoDB removed; container names use ${CONTAINER_PREFIX:-})
|   |-- docker-compose.override.yaml  Local build, Mongo URI, librechat.yaml mount
|   |-- librechat.yaml              App configuration
|   `-- .env.example                Template. The real .env is never committed.
|-- gateway/                        FastAPI gateway (main.py, model_registry.py, routing.py,
|                                   ollama_client.py, docling_client.py, token_probe.py)
|-- docling_service/                Docling conversion service (main.py)
|-- ocr_adapter/                    Mistral-OCR-compatible adapter (main.py)
|-- modelfiles/quick/               Ollama Modelfiles (qwen3-8b and ministral3-8b are in use;
|                                   other folders are test candidates)
`-- testing/                        Model test runners, results, document test tools
```

`mongo-data/` (the MongoDB data directory) exists only on the machine that runs the database and is never committed.

---

## 4. Prerequisites

- Windows 10 or 11 with PowerShell. All commands below are PowerShell. The pilot machine is Windows.
- Docker Desktop with the WSL2 backend.
- Python 3.13.
- Ollama for Windows (runs as a tray application) and a current NVIDIA driver.
- Git.
- Disk: about 40 GB free (model weights, Docker images, the LibreChat build).
- Memory: the LibreChat image build compiles the whole frontend and needs several GB free for Docker.

A GPU is needed only for the model runtime. LibreChat, MongoDB and the sign-in flow run without one.

---

## 5. Setup from a fresh clone

Replace `<repo>` with the path of the clone.

### 5.1 Ollama

Set the server environment for the Windows user, then quit and reopen Ollama from the system tray so it picks the values up:

```powershell
setx OLLAMA_FLASH_ATTENTION 1
setx OLLAMA_KV_CACHE_TYPE q8_0
```

Pull the base models and create the two Clarisync models from the Modelfiles:

```powershell
cd <repo>
ollama pull qwen3:8b
ollama pull ministral-3:8b
ollama create quick-qwen3-8b -f modelfiles/quick/qwen3-8b/Modelfile
ollama create quick-ministral3-8b -f modelfiles/quick/ministral3-8b/Modelfile
ollama list
```

`ollama list` must show both `quick-qwen3-8b` and `quick-ministral3-8b`.

### 5.2 MongoDB

LibreChat's own bundled MongoDB service is removed from `LibreChat/docker-compose.yml`. The database is a separate container named `clarisync-mongo`, created once by hand, with authentication on.

```powershell
docker run -d --name clarisync-mongo --restart unless-stopped `
  -p 127.0.0.1:27017:27017 `
  -v "<data-dir>\mongo-data:/data/db" `
  -e MONGO_INITDB_ROOT_USERNAME=clarisync-admin `
  -e MONGO_INITDB_ROOT_PASSWORD=<choose-a-password> `
  mongo:8.0
```

`<data-dir>` is any folder outside the repository. The container is not part of `docker compose`, so `restart unless-stopped` is what brings it back after a Docker or host restart. The prod stack uses its own instance (`clarisync-mongo-prod`, port 27018).

### 5.3 LibreChat environment file

`LibreChat/.env` is never committed. Get the working file from the maintainers (shared outside git) and place it at `LibreChat\.env`.

To build one from scratch instead, start from LibreChat's template:

```powershell
cd <repo>\LibreChat
Copy-Item .env.example .env
```

Generate random values with this helper (run it once per value):

```powershell
function New-Hex($bytes) { $b = New-Object byte[] $bytes; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); ($b | ForEach-Object { $_.ToString('x2') }) -join '' }
New-Hex 32   # 64 hex characters
New-Hex 16   # 32 hex characters
```

Keys the stack depends on (for a from-scratch file, or to check the supplied one):

| Key | Value |
|---|---|
| `PORT` | `3081` |
| `MONGO_URI` | `mongodb://clarisync-admin:<url-encoded-password>@host.docker.internal:27017/LibreChat?authSource=admin` |
| `CREDS_KEY` | 64 hex characters |
| `CREDS_IV` | 32 hex characters |
| `JWT_SECRET` | 64 hex characters |
| `JWT_REFRESH_SECRET` | 64 hex characters |
| `MEILI_MASTER_KEY` | random string |
| `ADMIN_PANEL_SESSION_SECRET` | random string |
| `POSTGRES_USER`, `POSTGRES_PASSWORD` | credentials for `vectordb` and `rag_api` (used by the override file) |
| `APP_TITLE` | `Clarisync Assistant` |
| `ENDPOINTS` | `custom` (shows only the Clarisync Gateway endpoint) |
| `SCHEDULES_SINGLE_PROCESS` | `true` (this deployment runs one process) |
| `ALLOW_SOCIAL_LOGIN`, `ALLOW_SOCIAL_REGISTRATION` | `true`, `false` (SAML on; first-time SAML users are still auto-created) |
| `ALLOW_EMAIL_LOGIN`, `ALLOW_REGISTRATION` | `false`, `false` (local login and registration off) |
| `ALLOW_EMAIL_LOGIN_OVERRIDE` | `true` (break-glass API login, logged) |
| `LOGIN_MAX`, `LOGIN_WINDOW` | LibreChat's local-login rate limiter. It also fires on the SAML route. Prod `LOGIN_MAX=7`, dev `20`. |
| `COMPOSE_PROJECT_NAME`, `CONTAINER_PREFIX`, `LIBRECHAT_IMAGE` | Prod only (`clarisync-prod`, `prod-`, `librechat-prod`). Never set `COMPOSE_PROJECT_NAME` on dev; it would orphan dev's volumes. |
| `OPENID_*` | leave empty. If OpenID is enabled, LibreChat disables SAML. |

The `SAML_*` keys are populated in the working `.env` (entry point, issuer, callback URL, certificate, session secret, and the email/given-name/surname claim mappings to Microsoft's default URNs). `SAML_CALLBACK_URL` must be absolute; a relative value fails with AADSTS7500511. See section 11.

Changes to `.env` are not picked up by `docker compose restart api`; use `docker compose up -d --force-recreate api`.

### 5.4 Python services

One virtual environment can serve all three services:

```powershell
cd <repo>
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install fastapi uvicorn requests python-multipart
pip install docling-slim==2.127.0
```

If PowerShell refuses to run `Activate.ps1` ("running scripts is disabled"), run `Set-ExecutionPolicy -Scope Process Bypass` in that window first. It applies only to that window.

Docling's scanned-PDF OCR uses RapidOCR with onnxruntime. If a scanned PDF fails on first use, run `pip install rapidocr onnxruntime`.

### 5.5 Build and start LibreChat

The `api` service is built from the local source, not pulled as an image. The first build is slow.

```powershell
cd <repo>\LibreChat
docker compose build api
docker compose up -d
docker ps
```

Expected containers: `LibreChat`, `admin-panel`, `chat-meilisearch`, `vectordb`, `rag_api`, plus the Mongo container from step 5.2. Container names are unprefixed on this stack. `docker compose` prints harmless `UID`/`GID` warnings on Windows.

If the page looks stale after a build, hard-refresh with Ctrl+F5 (section 9).

### 5.6 Start the Python services

On the pilot machine these run as NSSM-managed Windows services (Automatic start, auto-restart, run as `.\AI`), all bound to `127.0.0.1`. They run from the prod repo and are shared by prod and dev.

| Service | Port | Notes |
|---|---|---|
| `clarisync-gateway` | 8000 | FastAPI gateway; depends on docling |
| `clarisync-docling` | 8001 | Document conversion (CPU) |
| `clarisync-ocr` | 8002 | Mistral-OCR-compatible adapter; depends on docling |
| `clarisync-gpulog` | - | `nvidia-smi` sample every 30 s to `logs\gpu_metrics.csv` |

After any gateway, Docling or OCR code change, from an elevated PowerShell:

```powershell
Restart-Service clarisync-gateway
Restart-Service clarisync-docling -Force   # -Force: it has dependents
Restart-Service clarisync-ocr
```

Logs are in `logs\<service>.log`, rotated at 10 MB.

To debug by hand, stop the service first (a manual `uvicorn` on a port already in use fails with error 10048), then run from the service's own folder (all three contain a `main.py`):

```powershell
cd <repo>\gateway
..\.venv\Scripts\Activate.ps1
uvicorn main:app --host 127.0.0.1 --port 8000
```

Use port 8001 (`docling_service`) and 8002 (`ocr_adapter`) for the others, and `Start-Service` when done. Do heavy dev testing outside pilot hours; prod shares the gateway and the single GPU.

### 5.7 Health checks

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health   # status ok, max_pages 30
Invoke-RestMethod http://127.0.0.1:8002/health   # status ok, docling_reachable True
Invoke-RestMethod http://127.0.0.1:8000/health   # status ok, ollama_reachable True, docling_reachable True
```

### 5.8 First login

1. Create the break-glass admin inside the LibreChat container. The first user on a fresh database gets role ADMIN:

   ```powershell
   docker exec -it LibreChat npm run create-user
   ```

2. Normal users open the app and click **Login with Microsoft** (section 11). Local email login is off; the break-glass account logs in through the API (`ALLOW_EMAIL_LOGIN_OVERRIDE`) and to the admin panel.
3. Send a test message. The first request loads the model and takes a few seconds.
4. Attach a PDF and an image to confirm the document and vision paths.
5. Admin panel: `http://127.0.0.1:3001`. It authenticates against this stack's user DB and requires the ADMIN role. To change the break-glass password: `npm run reset-password` inside the container.

---

## 6. Ports

| Port | Service | Bind | Notes |
|---|---|---|---|
| 3080 | Prod LibreChat | all interfaces (Docker) | User-facing; the only externally reachable listener |
| 3081 | Dev LibreChat | `127.0.0.1` | |
| 3000 | Prod admin panel | `127.0.0.1` | Roles and permissions |
| 3001 | Dev admin panel | `127.0.0.1` | |
| 8000 | Gateway | `127.0.0.1` | No authentication; shared by prod and dev |
| 8001 | Docling service | `127.0.0.1` | No authentication. Never expose. |
| 8002 | OCR adapter | `127.0.0.1` | Static bearer key only |
| 11434 | Ollama | `127.0.0.1` | Native Windows application |
| 27018 | `clarisync-mongo-prod` | `127.0.0.1` | Authenticated |
| 27017 | `clarisync-mongo` (dev) | `127.0.0.1` | Authenticated |

The containers reach the gateway and OCR adapter through `host.docker.internal`.

---

## 7. Configuration reference

| File | Purpose |
|---|---|
| `LibreChat/.env` | Secrets and switches. Untracked. Template: `.env.example`. Changes need `docker compose up -d --force-recreate api`. |
| `LibreChat/librechat.yaml` | Endpoint, model spec, hidden UI features, OCR, file routing, registration. Bind-mounted; `docker compose restart api` applies changes. |
| `LibreChat/docker-compose.override.yaml` | Local image build (`${LIBRECHAT_IMAGE:-librechat}`), `MONGO_URI` passthrough, the `librechat.yaml` mount, `vectordb` credentials. |
| `LibreChat/client/index.html`, `client/public/assets/` | Branding source (theme CSS, logos, favicons, fonts). Baked into the build; changes need a rebuild. |
| `LibreChat/branding/` | Reference copy only. Not read by the build. |
| `gateway/model_registry.py` | The only place models are defined: Ollama tag, context size, whether loaded at startup. |
| `modelfiles/quick/*/Modelfile` | System prompt, sampling parameters and `num_ctx` per model. These values are load-bearing because the gateway does not send them per request. |

**`librechat.yaml` blocks that matter**

- `endpoints.custom`: one endpoint, "Clarisync Gateway", `baseURL: http://host.docker.internal:8000/v1`, model `quick-text`.
- `modelSpecs`: one spec, "Quick", with `enforce: true`, which hides the raw endpoint and model selector.
- `interface`: developer features hidden (agents, prompts, memories, web search, code runner, MCP, bookmarks, multi-conversation). `feedback` stays on because the pilot metrics depend on thumbs up/down. Shared links are not switched off (`sharedLinks` is commented out); a shared link still requires login.
- `modelSpecs[].preset.promptPrefix` is sent as a system message and replaces the Modelfile `SYSTEM` text on the pilot path. Modelfile parameters and the model tag still apply. Keep `promptPrefix` and `modelfiles/quick/qwen3-8b/Modelfile` in sync.
- `ocr` and `fileConfig`: send DOCX, XLSX and PPTX through the OCR adapter and mark PPTX as a text-delivery type.
- `registration.socialLogins`: providers offered on the login page.

**Gateway environment variables** (set in the PowerShell window that starts it; they persist in that window after Ctrl+C)

| Variable | Effect |
|---|---|
| `GATEWAY_ERROR_MODE` | `http` (default) returns HTTP errors. `reply` returns the same text as an assistant message. |
| `GATEWAY_DUMP_DIR` | Saves every request as JSON in that folder. Developer option. It writes conversation text to disk. Delete the folder afterwards and never commit it. |

**OCR adapter environment variables:** `DOCLING_URL` (default `http://127.0.0.1:8001`), `OCR_ADAPTER_API_KEY` (default `clarisync-ocr-local`, must equal `ocr.apiKey` in `librechat.yaml`), `CONVERT_TIMEOUT_S` (default 300).

**Limits in code:** Ollama request timeout 180 s (`gateway/ollama_client.py`), Docling conversion timeout 300 s, 30 pages and 25 MB per document (`docling_service/main.py`).

---

## 8. Changes made to upstream LibreChat

`LibreChat/` is a full copy of LibreChat (v0.8.8-rc2) with the changes below. Anyone upgrading LibreChat must re-apply them.

| File | Change |
|---|---|
| `docker-compose.yml` | Bundled `mongodb` service and its `depends_on` entry removed (Compose override files cannot remove a service). Container names use `${CONTAINER_PREFIX:-}` so prod and dev can coexist. Re-apply if the file is replaced. |
| `docker-compose.override.yaml` | `api` built locally (`image: ${LIBRECHAT_IMAGE:-librechat}`, `build.target: node`), `MONGO_URI` from `.env`, `librechat.yaml` mount only, `vectordb` credentials from `.env`. |
| `api/server/controllers/agents/client.js` | `getUserFacingRequestError` returns the bare message and strips a leading HTTP status code. |
| `client/src/components/Messages/Content/Error.tsx` | Error text shown without the "Something went wrong" wrapper; leading status code stripped. |
| `client/src/components/UnifiedSidebar/ConversationsSection.tsx` | Logo and wordmark row, labelled "New chat" button, persistent light/dark toggle. |
| `client/src/components/Auth/AuthLayout.tsx` | Login logo moved into the centred block above the heading. |
| `client/src/components/Chat/Messages/HoverButtons.tsx` | Edit button hidden on assistant messages (`isCreatedByUser` added to its condition). UI only; the API route still accepts edits. |
| `client/src/data-provider/mutations.ts` | Removed the ungated `useConversationTagsQuery()` call from `useTagConversationMutation` (now invalidates the `conversationTags` query). Fixes the `[BOOKMARKS] Forbidden /api/tags` noise for USER-role accounts. |
| `api/strategies/samlStrategy.js` | `user.id = user._id.toString()` added in `createSamlCallback`. Fixes the `checkBan` error "key.startsWith is not a function". |
| `client/index.html`, `client/public/assets/` | Clarisync branding: title, meta, loading colours, theme CSS link, logos, favicons, fonts. Diverges from upstream; expect a merge conflict on upgrade. |
| `client/src/locales/en/translation.json` | "Projects" displayed as "Folders" (32 values; keys unchanged). |
| `librechat.yaml` | Full Clarisync configuration (section 7). |

Sign-in is configured through `.env`. The one source patch it needs is `api/strategies/samlStrategy.js` (above).

---

## 9. Rebuilding and branding

Branding is baked into the client build. The old `branding/index.html` bind mount and its hashed-filename regeneration step are retired. `LibreChat/branding/` is a reference copy only (its `index.html` is stale and unused). The build reads `client/index.html` and `client/public/assets/` (`clarisync-theme.css`, favicons, apple-touch icon, `logo-mark.svg`, `logo.svg` (a copy of `logo-mark.svg`), `fonts/`), so branding edits go there, followed by a rebuild.

Run these from the `LibreChat` folder of the repo you changed:

| Change | Command |
|---|---|
| `librechat.yaml` | `docker compose restart api` (wait about 20 seconds) |
| `.env`, or a new/changed volume mount | `docker compose up -d --force-recreate api` |
| `client/src`, `client/index.html`, `client/public/assets`, `api/strategies/samlStrategy.js` | `docker compose build api`, then `docker compose up -d` |
| Gateway, Docling, OCR adapter | `Restart-Service` (shared by prod and dev; section 5.6) |

After a build, check `docker images` to confirm the new image id, then press Ctrl+F5 in the browser. LibreChat's service worker can serve the previous build. If the page is blank or requests 404 on an old hashed file, open DevTools, Application, Service Workers, Unregister, then Storage, Clear site data. This also logs the user out and resets the saved theme.

Brand colours: teal `#1F4756`, page background `#F7F8F8`, text `#14262C`. Poppins is the intended heading font.

---

## 10. Daily operation

| | Prod (pilot) | Dev |
|---|---|---|
| Repo | `self-hosted-llm` | `selfhostedllmproject` |
| LibreChat / admin panel | 3080 / 3000 | 3081 / 3001 |
| Containers | `prod-` prefix | original names |
| MongoDB | `clarisync-mongo-prod` (27018, `--auth`) | `clarisync-mongo` (27017) |
| Image | `librechat-prod` | `librechat` |
| `LOGIN_MAX` | 7 | 20 |

Both stacks share the native services (gateway, Docling, OCR adapter, Ollama) and the single GPU. They also share `localhost` cookies across ports, so use separate browser profiles.

**After a machine restart.** Docker Desktop and Ollama start when `AI` signs in, not at boot, and auto-login is off. RDP in as `AI`. The containers use `restart: always` (Mongo uses `unless-stopped`) and come back on their own; the NSSM services start automatically. **Always disconnect the RDP session; never sign out of `AI`.**

**Maintenance stop:** `docker compose down` in each stack, `Stop-Service` for the clarisync services (elevated; Docling needs `-Force`).

**Rules**

- Restart the affected service after any gateway, Docling or OCR change (section 5.6).
- After restarting Docling, the first conversion of each file is slow again, because its cache is in memory.
- Restart rules for LibreChat are in section 9.

**Useful commands** (run from the prod repo unless noted)

```powershell
Get-Service clarisync-*
docker ps
Get-Content gateway\gateway_metrics.jsonl -Tail 6             # recent request timings
Get-Content logs\gpu_metrics.csv -Tail 5                       # GPU samples
docker logs LibreChat --tail 120                          # this stack's log (timestamps are UTC)
docker logs LibreChat --since 3h 2>&1 | Select-String "ocr|error"
docker logs rag_api --since 3h
ollama ps
```

To confirm the OCR adapter handled an Office file, look for an `[ocr] upload ...` line in `logs\clarisync-ocr.log`. If the adapter is down, LibreChat silently falls back to its own parser for DOCX and XLSX.

## 11. Sign-in (SAML)

Sign-in is handled entirely by LibreChat's built-in SAML support against Microsoft Entra ID. The gateway, Docling service and OCR adapter are not involved and never see who is logged in. The protocol is SAML, not OIDC.

**Architecture.** This deployment has no SSO broker in front of it, unlike Clarisync's other (Laravel/Angular) products, which sit behind an internal broker service on port 8000. LibreChat talks to Entra directly — it is both the relying-party app and the thing that constructs and validates the SAML flow. The port 8000 gateway in this stack is the unrelated FastAPI request router described in section 2; it has no role in authentication.

**Current state.** SAML login works on both stacks (prod on `localhost:3080`, dev on `localhost:3081`), verified with real Clarisync accounts. `SAML_IDP_ISSUER` is set to Entra's tenant STS issuer and tampered assertions are rejected. The signing certificate is valid until October 2028. Anyone within Clarisync may sign in: no security group or "Assignment required" is used.

**Verified behaviour**

- A new Entra user is auto-created as provider `saml`, role USER (`ALLOW_SOCIAL_REGISTRATION=false` does not block first-time SAML users).
- An existing local account with the same email is refused ("SAML login conflicts with existing provider: local"; no merge). Keep local accounts to the break-glass admin only.
- Logout works.
- The login page shows only "Login with Microsoft" (`SAML_BUTTON_LABEL`, `SAML_IMAGE_URL`).
- Seamless SSO re-logs in with the device's Entra account and shows no account picker. `forceAuthn` exists in passport-saml but is not exposed in this fork. To test as another user, use a separate Windows profile, another machine, or a `netsh portproxy` from the tester's laptop (`127.0.0.1:3080` to `192.168.90.22:3080`; remove afterwards).

**Entra rule: Identifier and Reply URL edits must append, never replace.** Replacing the `localhost:3080` entry with 3081 broke prod login (AADSTS700016) until it was re-added. Keep `http://localhost:3080`, `http://localhost:3081` and add the `https://192.168.90.22` entries alongside. Entra rejects `http://` Reply URLs other than localhost, so pointing `.env` at the LAN IP over plain HTTP does not work.

**Move to HTTPS (pending).** Once HTTPS is up on `192.168.90.22` and the Entra entries are appended (Identifier `https://192.168.90.22`, Reply URL `https://192.168.90.22/oauth/saml/callback`), set these in the prod `.env`: `DOMAIN_CLIENT`, `DOMAIN_SERVER`, `SAML_ISSUER` and `SAML_CALLBACK_URL` to the HTTPS address, plus `SESSION_COOKIE_SECURE=true`. Then run `docker compose up -d --force-recreate api`. The TLS proxy must pass `X-Forwarded-For`. Be careful with HSTS on a self-signed certificate. Dev stays on `localhost:3081`.

---

## 12. Security notes

- **Secrets** live in `LibreChat/.env` only. It is ignored by git. Never commit `.env`, certificates, `gateway/gateway_dump/` or `gateway/gateway_metrics.jsonl`.
- **Network exposure.** Only LibreChat on 3080 listens on all interfaces. The gateway, Docling, OCR adapter, Ollama, both MongoDB instances and both admin panels are bound to `127.0.0.1`. Still open: RDP (3389), AnyDesk (7070) and Zabbix (10050) have inbound allow rules on all profiles, and SMB/RPC/NetBIOS listen beyond localhost. Scoping them needs the office IP ranges. Go-live needs confirmation that only 443 to LibreChat is exposed externally.
- **HTTPS.** Not yet in place; until it is, the app is served over plain HTTP and reachable on the LAN only (section 11).
- **Local login** is off except the break-glass admin (`ALLOW_EMAIL_LOGIN_OVERRIDE`, logged). Registration is off.
- **Shared links** are not disabled; a shared link still requires login.
- **Docling** has no authentication and must stay on `127.0.0.1`.
- **Development defaults to replace before wider use:** `ocr.apiKey` in `librechat.yaml` and `OCR_ADAPTER_API_KEY` (`clarisync-ocr-local`). LibreChat prints the resolved `ocr:` block, including the key, in its startup log.
- **Document text in memory:** the Docling cache holds up to 32 converted documents and the OCR adapter up to 50 uploads (15-minute expiry) until restart.
- **Deletion:** deleting a conversation in LibreChat hard-deletes it and its messages from MongoDB.
- **Licensing:** MongoDB is used internally and not offered as a service, which is within the SSPL exemption.

---

## 13. Known issues and limitations

- **Streaming is simulated.** The user sees the answer arrive in one piece.
- **Single card, single resident model.** Image requests pay a model-swap delay of several seconds.
- **Unsupported file types.** LibreChat gives some types no delivery path (archives, other presentation formats) and drops them without an error. The model may then invent an answer.
- **Office files** have no gateway page limit. Only the size guard applies.
- **Unknown company terms.** The model can invent answers about Clarisync-specific terms. Phase 2 retrieval is the intended fix.
- **Dev credential-fingerprint mismatch.** Dev's LibreChat logs a mismatch (`CREDS_KEY`/`CREDS_IV`/JWT secrets vs the DB record) on every start. Do not overwrite the DB marker. Prod is unaffected.
- **Seamless SSO.** The device's Entra account is reused with no picker (section 11).
- **Restart gap.** After a machine restart Docker and Ollama stay down until someone RDPs in as `AI` (section 10).
- **`wslrelay` phantom listener.** After `wsl --shutdown` or a rebuild, a second process can hold port 3080 on `[::1]` and serve stale content (section 14).
- **Two databases.** Postgres/pgvector runs alongside MongoDB for LibreChat's native file-upload feature. MongoDB is the planned single database.
- **Gateway and LiteLLM.** The custom gateway is the interim routing layer. LiteLLM returns if a second serving backend is added.

---

## 14. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| "The selected model is unavailable from this provider" | A different service is answering on port 8000 (started from the wrong folder). Restart the gateway from `gateway\`. |
| OCR adapter logs `Docling rejected ... 404` | The Docling port is answered by the gateway. Restart each service from its own folder on its own port. |
| Blank page or old UI after a rebuild | Stale service worker: Ctrl+F5, then unregister it (section 9). |
| `localhost:3081` shows old content, `docker ps` looks correct | `netstat -ano \| findstr :3081`. If a `[::1]` listener belongs to `wslrelay.exe`, run `Stop-Process -Id <pid> -Force`. |
| LibreChat crash-loops with `ECONNREFUSED` to Mongo | This stack's Mongo container is stopped. `docker start clarisync-mongo`. |
| DOCX answers work but no `[ocr]` line appears | The adapter is down and LibreChat used its own parser. |
| Config change has no effect | `librechat.yaml`: `docker compose restart api`. `.env` or compose/mount changes: `docker compose up -d --force-recreate api`. Source or branding changes: `docker compose build api` then `up -d`. |
| Edited file shows old content | Read it back from disk (`Select-String -Path <file> -Pattern "<new text>"`). Editors can display a save that did not persist. |
| "Too many login attempts" on SAML login | LibreChat's local-login rate limiter (`LOGIN_MAX`/`LOGIN_WINDOW`) firing on the SAML route. Raise `LOGIN_MAX`, then force-recreate `api`. |
| AADSTS700016 "Application with identifier ... was not found" | The Entra Identifier for that origin is missing (an edit replaced it instead of appending). Ask the Entra admin to re-add it (section 11). |
| AADSTS7500511 | `SAML_CALLBACK_URL` is relative. Use the absolute URL. |

---

## 15. Testing

- `testing/model_results/`: text and vision test runners (`test_runner.py`, `vision_test_runner.py`) and stored results from the six-model comparison that selected `qwen3-8b`.
- `testing/docling/`: document test tools, including `compare_pptx.py` and the test PPTX generator.
- Check a running stack with the health calls in section 5.7 and by attaching one file of each type.

---

## 16. Maintainers

| Name | Email |
|---|---|
| Ryef Taimur | taimur.nawaz@clarisync.com |
| Ibrahim Murtaza | ibrahim.murtaza@clarisync.com |