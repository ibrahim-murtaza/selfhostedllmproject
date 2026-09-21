"""
OCR adapter -- a small Mistral-OCR-compatible front for the local Docling
service, so LibreChat's built-in `ocr:` setting can use Docling instead of
Mistral's cloud API (nothing leaves the machine).

LibreChat (strategy `mistral_ocr` with a custom baseURL) makes four calls for
every file, all with `Authorization: Bearer <key>`:

    POST   /v1/files              multipart: purpose=ocr, file=<bytes>  -> {"id": ...}
    GET    /v1/files/{id}/url     ?expiry=N                             -> {"url": ...}
    POST   /v1/ocr                {model, document:{type, <type>: url}} -> {"pages": [{"markdown": ...}]}
    DELETE /v1/files/{id}

This adapter keeps the uploaded bytes in memory, hands back an opaque URL that
points at itself, and on /v1/ocr sends the bytes to Docling's /convert
(`docling_service`, default http://127.0.0.1:8001). Docling returns the whole
document as one Markdown string, so the result is a single "page".

Nothing is written to disk. Files are removed when LibreChat deletes them, or
after FILE_TTL_S if it never does.

Run (from THIS folder -- three services each have a main.py):
    pip install fastapi uvicorn requests python-multipart
    uvicorn main:app --host 0.0.0.0 --port 8002

0.0.0.0 is needed so the LibreChat container can reach it as
host.docker.internal:8002. The bearer key is a light guard, not real security:
keep the port off any network you don't trust.

Environment variables (all optional):
    DOCLING_URL            default http://127.0.0.1:8001
    OCR_ADAPTER_API_KEY    default clarisync-ocr-local (must match `ocr.apiKey`)
    CONVERT_TIMEOUT_S      default 300 (same as the gateway)
"""

import os
import re
import threading
import time
import uuid

import requests
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

DOCLING_URL = os.environ.get("DOCLING_URL", "http://127.0.0.1:8001").rstrip("/")
API_KEY = os.environ.get("OCR_ADAPTER_API_KEY", "clarisync-ocr-local")
CONVERT_TIMEOUT_S = int(os.environ.get("CONVERT_TIMEOUT_S", "300"))
FILE_TTL_S = 15 * 60  # forget uploads LibreChat never deleted
MAX_FILES = 50

app = FastAPI()

_files: dict[str, dict] = {}
_lock = threading.Lock()


@app.exception_handler(HTTPException)
async def mistral_shaped_errors(request: Request, exc: HTTPException):
    """LibreChat reads `message` from the error body (Mistral's error shape)."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "object": "error",
            "message": exc.detail,
            "type": "invalid_request_error" if exc.status_code < 500 else "server_error",
            "code": exc.status_code,
        },
    )


def _check_auth(request: Request) -> None:
    if request.headers.get("authorization", "") != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


def _prune() -> None:
    """Drop expired uploads, then the oldest ones if there are too many. Caller holds _lock."""
    now = time.time()
    for fid in [f for f, v in _files.items() if now - v["created"] > FILE_TTL_S]:
        del _files[fid]
    while len(_files) > MAX_FILES:
        del _files[min(_files, key=lambda f: _files[f]["created"])]


def _ascii_name(name: str) -> str:
    """Docling reads the format from the extension; HTTP headers must be ASCII."""
    base, ext = os.path.splitext(name or "")
    base = base.encode("ascii", "ignore").decode() or "document"
    ext = ext.encode("ascii", "ignore").decode()
    return base + ext


def _convert(name: str, data: bytes) -> dict:
    """Send the bytes to Docling. Raises HTTPException with a plain reason."""
    try:
        r = requests.post(
            f"{DOCLING_URL}/convert",
            data=data,
            headers={
                "X-Filename": _ascii_name(name),
                "Content-Type": "application/octet-stream",
            },
            timeout=(5, CONVERT_TIMEOUT_S),
        )
    except (requests.ConnectionError, requests.ConnectTimeout) as e:
        print(f"[ocr] Docling unreachable: {e}")
        raise HTTPException(status_code=503, detail="The document converter is not running.")
    except requests.ReadTimeout:
        raise HTTPException(
            status_code=504,
            detail=f"Conversion took longer than {CONVERT_TIMEOUT_S} seconds.",
        )
    if r.status_code == 200:
        return r.json()
    try:
        reason = r.json()["error"]["message"]
    except Exception:
        reason = (r.text or "").strip()[:300] or f"HTTP {r.status_code}"
    print(f"[ocr] Docling rejected {name!r}: {r.status_code} {reason}")
    raise HTTPException(status_code=422 if r.status_code == 422 else r.status_code, detail=reason)


# --- POST /v1/files ----------------------------------------------------------
@app.post("/v1/files")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    purpose: str = Form("ocr"),
):
    _check_auth(request)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    fid = uuid.uuid4().hex
    with _lock:
        _prune()
        _files[fid] = {"name": file.filename or "document", "data": data, "created": time.time()}
    print(f"[ocr] upload {file.filename!r} ({len(data):,} bytes) -> {fid[:8]}")
    return {
        "id": fid,
        "object": "file",
        "bytes": len(data),
        "created_at": int(time.time()),
        "filename": file.filename,
        "purpose": purpose,
        "sample_type": "ocr_input",
        "source": "upload",
    }


# --- GET /v1/files/{id}/url ---------------------------------------------------
@app.get("/v1/files/{file_id}/url")
def signed_url(file_id: str, request: Request, expiry: int = 24):
    _check_auth(request)
    with _lock:
        if file_id not in _files:
            raise HTTPException(status_code=404, detail="File not found.")
    # Opaque: only this adapter ever reads it back (in /v1/ocr below).
    base = str(request.base_url).rstrip("/")
    return {"url": f"{base}/v1/files/{file_id}/content"}


# --- POST /v1/ocr -------------------------------------------------------------
class OcrRequest(BaseModel):
    model: str | None = None
    document: dict


_ID_RE = re.compile(r"/v1/files/([0-9a-f]{32})/")


@app.post("/v1/ocr")
def ocr(body: OcrRequest, request: Request):
    _check_auth(request)
    url = body.document.get("document_url") or body.document.get("image_url") or ""
    if isinstance(url, dict):  # Mistral also allows {"url": ...}
        url = url.get("url", "")
    m = _ID_RE.search(str(url))
    if not m:
        raise HTTPException(status_code=400, detail="Unknown document URL.")
    with _lock:
        entry = _files.get(m.group(1))
    if entry is None:
        raise HTTPException(status_code=404, detail="File not found or expired.")

    start = time.monotonic()
    result = _convert(entry["name"], entry["data"])
    markdown = result.get("markdown", "")
    print(
        f"[ocr] {entry['name']!r}: {len(markdown):,} chars in "
        f"{(time.monotonic() - start) * 1000:.0f} ms"
        f"{' (cached)' if result.get('cached') else ''}"
    )
    return {
        "pages": [{"index": 0, "markdown": markdown, "images": [], "dimensions": None}],
        "model": body.model or "docling",
        "usage_info": {"pages_processed": 1, "doc_size_bytes": len(entry["data"])},
    }


# --- DELETE /v1/files/{id} ----------------------------------------------------
@app.delete("/v1/files/{file_id}")
def delete_file(file_id: str, request: Request):
    _check_auth(request)
    with _lock:
        existed = _files.pop(file_id, None) is not None
    return {"id": file_id, "object": "file", "deleted": existed}


@app.get("/health")
def health():
    try:
        ok = requests.get(f"{DOCLING_URL}/health", timeout=3).status_code == 200
    except requests.RequestException:
        ok = False
    return {"status": "ok" if ok else "degraded", "docling_reachable": ok, "files_held": len(_files)}