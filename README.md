# Clarisync In-House LLM Platform

A self-hosted AI chat platform for Clarisync employees. It runs on company hardware so confidential work stays inside Clarisync's infrastructure instead of going to public AI tools.

| Layer | Component |
|---|---|
| Interface | LibreChat (patched, built locally) |
| Routing | Custom FastAPI gateway |
| Model serving | Ollama |
| Document reading | Docling (CPU only) behind two small FastAPI services |
| Data | MongoDB (chats, users), Postgres/pgvector (LibreChat's native file-upload feature only) |
| Sign-in | Microsoft Entra ID over SAML (not configured yet, see `docs/SSO_INTEGRATION.md`) |

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
- Branding: applied. Font files and welcome/footer text are not supplied.
- SAML sign-in: not configured. Local email login is active.
- Network exposure of the gateway, OCR adapter and MongoDB ports: open item (section 12).
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
|-- docs/
|   `-- SSO_INTEGRATION.md          Guide for the SAML work
|-- LibreChat/                      Patched LibreChat source and deployment config
|   |-- api/  client/  packages/    Upstream source (patched files listed in section 8)
|   |-- branding/                   Theme CSS, logo, favicons, index.html (bind-mounted into the container)
|   |-- docker-compose.yml          Upstream compose file (bundled MongoDB service removed)
|   |-- docker-compose.override.yaml  Local build, Mongo URI, branding mounts
|   |-- librechat.yaml              App configuration
|   `-- .env.example                Template. The real .env is never committed.
|-- gateway/                        FastAPI gateway (main.py, model_registry.py, routing.py,
|                                   ollama_client.py, docling_client.py, token_probe.py)
|-- docling_service/                Docling conversion service (main.py)
|-- ocr_adapter/                    Mistral-OCR-compatible adapter (main.py)
|-- modelfiles/quick/               Ollama Modelfiles (qwen3-8b and ministral3-8b are in use;
|                                   other folders are test candidates)
|-- testing/                        Model test runners, results, document test tools
`-- design/                         UI design notes
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
  -p 27017:27017 `
  -v "<data-dir>\mongo-data:/data/db" `
  -e MONGO_INITDB_ROOT_USERNAME=clarisync-admin `
  -e MONGO_INITDB_ROOT_PASSWORD=<choose-a-password> `
  mongo:8.0
```

`<data-dir>` is any folder outside the repository. The container is not part of `docker compose`, so `restart unless-stopped` is what brings it back after a Docker or host restart.

### 5.3 LibreChat environment file

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

Set these keys in `LibreChat/.env`:

| Key | Value |
|---|---|
| `PORT` | `3080` |
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
| `ALLOW_SOCIAL_LOGIN` | `false` until SAML is configured |
| `OPENID_*` | leave empty. If OpenID is enabled, LibreChat disables SAML. |

Leave the `SAML_*` keys empty until the SAML work starts (`docs/SSO_INTEGRATION.md`).

### 5.4 Python services

One virtual environment can serve all three services:

```powershell
cd <repo>
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install fastapi uvicorn requests python-multipart
pip install docling-slim==2.127.0
```

Docling's scanned-PDF OCR uses RapidOCR with onnxruntime. If a scanned PDF fails on first use, run `pip install rapidocr onnxruntime`.

### 5.5 Build and start LibreChat

The `api` service is built from the local source, not pulled as an image. The first build is slow.

```powershell
cd <repo>\LibreChat
docker compose build api
docker compose up -d
docker ps
```

Expected containers: `LibreChat`, `admin-panel`, `chat-meilisearch`, `vectordb`, `rag_api`, plus `clarisync-mongo` from step 5.2. `docker compose` prints harmless `UID`/`GID` warnings on Windows.

If the page is blank after the first build, regenerate `branding/index.html` (section 9).

### 5.6 Start the Python services

Use a separate PowerShell window per service, each started from its own folder, in this order. All three folders contain a `main.py`, so starting from the wrong folder runs the wrong service.

```powershell
# Window 1: Docling. Wait for "[docling] models warmed".
cd <repo>\docling_service
..\.venv\Scripts\Activate.ps1
uvicorn main:app --host 127.0.0.1 --port 8001

# Window 2: OCR adapter
cd <repo>\ocr_adapter
..\.venv\Scripts\Activate.ps1
uvicorn main:app --host 0.0.0.0 --port 8002

# Window 3: gateway
cd <repo>\gateway
..\.venv\Scripts\Activate.ps1
uvicorn main:app --host 0.0.0.0 --port 8000
```

The gateway and OCR adapter bind `0.0.0.0` because the LibreChat container reaches them as `host.docker.internal`. See section 12 before exposing the machine to a wider network.

### 5.7 Health checks

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health   # status ok, max_pages 30
Invoke-RestMethod http://127.0.0.1:8002/health   # status ok, docling_reachable True
Invoke-RestMethod http://127.0.0.1:8000/health   # status ok, ollama_reachable True, docling_reachable True
```

### 5.8 First login

1. Open `http://localhost:3080`.
2. Register an account. The first account registered on a fresh database becomes the administrator.
3. Send a test message. The first request loads the model and takes a few seconds.
4. Attach a PDF and an image to confirm the document and vision paths.
5. The admin panel is at `http://localhost:3000`.

---

## 6. Ports

| Port | Service | Bind | Notes |
|---|---|---|---|
| 3080 | LibreChat | all interfaces (Docker) | User-facing |
| 3000 | Admin panel | all interfaces (Docker) | Roles and permissions |
| 8000 | Gateway | `0.0.0.0` | No authentication |
| 8001 | Docling service | `127.0.0.1` | No authentication. Never expose. |
| 8002 | OCR adapter | `0.0.0.0` | Static bearer key only |
| 11434 | Ollama | localhost | Native Windows application |
| 27017 | `clarisync-mongo` | all interfaces (Docker) | Authenticated, but reachable from the network |

---

## 7. Configuration reference

| File | Purpose |
|---|---|
| `LibreChat/.env` | Secrets and switches. Untracked. Template: `.env.example`. |
| `LibreChat/librechat.yaml` | Endpoint, model spec, hidden UI features, OCR, file routing, registration. Bind-mounted; `docker compose restart api` applies changes. |
| `LibreChat/docker-compose.override.yaml` | Local image build, `MONGO_URI` passthrough, branding mounts, `vectordb` credentials. |
| `LibreChat/branding/` | `clarisync-theme.css`, `logo.svg`, favicons, `index.html`, `fonts/`. |
| `gateway/model_registry.py` | The only place models are defined: Ollama tag, context size, whether loaded at startup. |
| `modelfiles/quick/*/Modelfile` | System prompt, sampling parameters and `num_ctx` per model. These values are load-bearing because the gateway does not send them per request. |

**`librechat.yaml` blocks that matter**

- `endpoints.custom`: one endpoint, "Clarisync Gateway", `baseURL: http://host.docker.internal:8000/v1`, model `quick-text`.
- `modelSpecs`: one spec, "Quick", with `enforce: true`, which hides the raw endpoint and model selector.
- `interface`: developer features hidden (agents, prompts, memories, web search, code runner, MCP, sharing, bookmarks). `feedback` stays on because the pilot metrics depend on thumbs up/down.
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
| `docker-compose.yml` | Bundled `mongodb` service and its `depends_on` entry removed (Compose override files cannot remove a service). Re-apply if the file is replaced. |
| `docker-compose.override.yaml` | `api` built locally (`image: librechat`, `build.target: node`), `MONGO_URI` from `.env`, branding bind mounts, `vectordb` credentials from `.env`. |
| `api/server/controllers/agents/client.js` | `getUserFacingRequestError` returns the bare message and strips a leading HTTP status code. |
| `client/src/components/Messages/Content/Error.tsx` | Error text shown without the "Something went wrong" wrapper; leading status code stripped. |
| `client/src/components/UnifiedSidebar/ConversationsSection.tsx` | Logo and wordmark row, labelled "New chat" button, persistent light/dark toggle. |
| `client/src/components/Auth/AuthLayout.tsx` | Login logo moved into the centred block above the heading. |
| `client/src/locales/en/translation.json` | "Projects" displayed as "Folders" (32 values; keys unchanged). |
| `librechat.yaml` | Full Clarisync configuration (section 7). |

Sign-in changes are configuration only (`.env`, `librechat.yaml`, optionally the override file). They need no source patch.

---

## 9. Rebuilding and branding

**No rebuild needed** for: `.env` or `librechat.yaml` changes (`docker compose restart api`, wait about 20 seconds), CSS variables, fonts, logo, favicons.

**Rebuild needed** for anything under `LibreChat/client/src` or `LibreChat/api`:

```powershell
cd <repo>\LibreChat
docker compose build api
docker compose up -d
```

**`branding/index.html` must be regenerated after every rebuild.** It is bind-mounted over the built `index.html` and hardcodes Vite's hashed asset filenames, which change when the source changes. A stale file gives a blank page.

1. Copy the freshly built file out of an image container (not the running container, whose `index.html` is the mounted copy):

   ```powershell
   docker create --name idx librechat
   docker cp idx:/app/client/dist/index.html <repo>\LibreChat\branding\index.html
   docker rm idx
   ```

2. Re-apply these six edits to `branding/index.html`:
   - `theme-color` meta: `#F7F8F8`
   - description meta: Clarisync-specific text
   - `<title>`: `Clarisync Assistant`
   - loading-screen background colours: normal dark `#0d0d0d` to `#0F1618`, normal light `#ffffff` to `#F7F8F8` (leave the high-contrast branches untouched)
   - add `<link rel="stylesheet" href="./assets/clarisync-theme.css">` after the app's own stylesheet link

3. `docker compose up -d` (not `restart`, because a mount changed).

**Browser side after a rebuild:** LibreChat's service worker can serve the previous build. If the page is blank or requests 404 on an old hashed file, open DevTools, Application, Service Workers, Unregister, then Storage, Clear site data. This also logs the user out and resets the saved theme.

Brand colours: teal `#1F4756`, page background `#F7F8F8`, text `#14262C`. Poppins is the intended heading font. The `.woff2` files are not in `branding/fonts/`.

---

## 10. Daily operation

**Start order**

1. Docker Desktop (wait for the engine).
2. Ollama (tray application).
3. `docker start clarisync-mongo` (it restarts by itself after a Docker restart).
4. `cd LibreChat; docker compose up -d`
5. Docling, then OCR adapter, then gateway (section 5.6).
6. Health checks (section 5.7).

**Stop:** Ctrl+C in each service window, `docker compose down`, `docker stop clarisync-mongo`.

**Rules**

- Restart the gateway after any code change (uvicorn runs without `--reload`).
- After restarting Docling, the first conversion of each file is slow again, because its cache is in memory.
- Restart `api` after any `librechat.yaml` change.

**Useful commands**

```powershell
Get-Content gateway\gateway_metrics.jsonl -Tail 6            # recent request timings
docker logs LibreChat --tail 120                              # LibreChat log (timestamps are UTC)
docker logs LibreChat --since 3h 2>&1 | Select-String "ocr|error"
docker logs rag_api --since 3h
```

To confirm the OCR adapter handled an Office file, look for an `[ocr] upload ...` line in the adapter window. If the adapter is down, LibreChat silently falls back to its own parser for DOCX and XLSX.

---

## 11. Sign-in (SAML)

Sign-in is handled entirely by LibreChat's built-in SAML support against Microsoft Entra ID. The gateway, Docling service and OCR adapter are not involved and never see who is logged in. The protocol is SAML, not OIDC.

Full instructions, the file map and the test plan are in `docs/SSO_INTEGRATION.md`.

---

## 12. Security notes

- **Secrets** live in `LibreChat/.env` only. It is ignored by git. Never commit `.env`, certificates, `gateway/gateway_dump/` or `gateway/gateway_metrics.jsonl`.
- **Network exposure (open item).** The gateway (8000), OCR adapter (8002) and MongoDB (27017) are reachable from the corporate network on the pilot machine. The gateway has no authentication. The OCR adapter accepts a static key. A Windows firewall rule scoped to the Python executable did not block LAN access in testing. Fix before real users are on the machine, for example by publishing Mongo's port on the internal Docker interface only and restricting 8000 and 8002 to the Docker subnet.
- **Docling** has no authentication and must stay on `127.0.0.1`.
- **Development defaults to replace before wider use:** `ocr.apiKey` in `librechat.yaml` and `OCR_ADAPTER_API_KEY` (`clarisync-ocr-local`). LibreChat prints the resolved `ocr:` block, including the key, in its startup log.
- **Document text in memory:** the Docling cache holds up to 32 converted documents and the OCR adapter up to 50 uploads (15-minute expiry) until restart.
- **Deletion:** deleting a conversation in LibreChat hard-deletes it and its messages from MongoDB.
- **Licensing:** MongoDB is used internally and not offered as a service, which is within the SSPL exemption.
- **User roles:** new-account role assignment after the first administrator is not verified on this build. Check it before go-live.

---

## 13. Known issues and limitations

- **Stale oversize-PDF message.** After one "has N pages" rejection in a conversation, later oversize PDFs in the same conversation can show the first file's message, whatever their real page count.
- **Streaming is simulated.** The user sees the answer arrive in one piece.
- **Single card, single resident model.** Image requests pay a model-swap delay of several seconds.
- **Unsupported file types.** LibreChat gives some types no delivery path (archives, other presentation formats) and drops them without an error. The model may then invent an answer.
- **Office files** have no gateway page limit. Only the size guard applies.
- **Unknown company terms.** The model can invent answers about Clarisync-specific terms. Phase 2 retrieval is the intended fix.
- **Font files, welcome text and footer text** are not supplied.
- **`wslrelay` phantom listener.** After `wsl --shutdown` or a rebuild, a second process can hold port 3080 on `[::1]` and serve stale content (section 14).
- **Two databases.** Postgres/pgvector runs alongside MongoDB for LibreChat's native file-upload feature. MongoDB is the planned single database.
- **Gateway and LiteLLM.** The custom gateway is the interim routing layer. LiteLLM returns if a second serving backend is added.

---

## 14. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| "The selected model is unavailable from this provider" | A different service is answering on port 8000 (started from the wrong folder). Restart the gateway from `gateway\`. |
| OCR adapter logs `Docling rejected ... 404` | The Docling port is answered by the gateway. Restart each service from its own folder on its own port. |
| Blank page after a rebuild | Stale `branding/index.html` or service worker (section 9). |
| `localhost:3080` shows old content, `docker ps` looks correct | `netstat -ano \| findstr :3080`. If a `[::1]` listener belongs to `wslrelay.exe`, run `Stop-Process -Id <pid> -Force`. |
| LibreChat crash-loops with `ECONNREFUSED` to Mongo | `clarisync-mongo` is stopped. `docker start clarisync-mongo`. |
| DOCX answers work but no `[ocr]` line appears | The adapter is down and LibreChat used its own parser. |
| Config change has no effect | `librechat.yaml` and `.env` need `docker compose restart api`. Compose file changes need `docker compose up -d`. Source changes need `docker compose build api`. |
| Edited file shows old content | Read it back from disk (`Select-String -Path <file> -Pattern "<new text>"`). Editors can display a save that did not persist. |

---

## 15. Testing

- `testing/model_results/`: text and vision test runners (`test_runner.py`, `vision_test_runner.py`) and stored results from the six-model comparison that selected `qwen3-8b`.
- `testing/docling/`: document test tools, including `compare_pptx.py` and the test PPTX generator.
- Check a running stack with the health calls in section 5.7 and by attaching one file of each type.

---

## 16. Maintainers

- Ibrahim Murtaza: model serving, LibreChat interface layer, resource management.
- Ryef Taimur Nawaz: identity and access, data and storage, gateway and routing, observability.