"""
FastAPI gateway -- OpenAI-compatible /v1/chat/completions endpoint that
LibreChat calls instead of hitting Ollama directly.

Scope:
- Streaming (stream:true) is supported via simulated SSE: the full
  response is generated normally (blocking), then sent back as a single
  delta chunk plus a finish chunk -- satisfies clients requiring an SSE
  shape without real token-by-token generation, which would require
  rewriting ollama_client.py to consume Ollama's own stream.
- Swap orchestration: explicitly unloads any other resident Quick model
  before loading a new one (deterministic, not relying on Ollama's
  idle-timeout auto-eviction -- see handoff note on why).
- Routing: Stage 1 (image-attached -> vision) is real; Stages 2-4 are
  no-ops (see routing.py) since only one text tier exists.
- Documents: LibreChat sends attachments as {"type": "file"} parts with the
  whole file base64-encoded, and resends them on EVERY turn. Each file part
  anywhere in the history is converted to markdown by the local Docling
  service (docling_client.py; results are cached there by file hash) and
  placed in the same message as the user's text.
- Every request logs swap type and Ollama's own reported timing
  (load/eval/total duration) to gateway_metrics.jsonl, for the
  response-latency success metric.

- Size guard: a prompt (document text included) that doesn't fit the model's
  context window is refused with a clear message instead of being sent to
  Ollama, which can shorten an over-long prompt without saying so. Big text
  prompts are measured exactly by Ollama itself (token_probe.py) because
  characters-per-token varies from ~5 (prose) to ~1.5 (number-heavy tables).

- Failures: problems the user can act on (unreadable or over-page-limit file,
  file too large, chat too long) are returned as HTTP 400 with an OpenAI-style
  error body, so LibreChat shows them in its error box straight away
  (LibreChat retries most other statuses several times before giving up; 400
  is on its no-retry list). Docling down / timeout / Ollama down are 503/504
  (retried by LibreChat, so the box appears after about a minute). All wording
  is plain language; technical detail (token counts, Docling's own message)
  goes only to gateway_metrics.jsonl. "reply" mode (GATEWAY_ERROR_MODE=reply)
  is a fallback that returns the same text as a plain assistant message.
  Every one is logged as event "gateway_reply". /health also reports
  docling_reachable.

- Document metrics: requests that carry documents also log doc_count,
  doc_chars, doc_wait_ms (wall time the gateway waited on Docling),
  doc_convert_ms (conversion time Docling itself reported; 0 on cache hits)
  and doc_cache_hits.

- Request capture (developer option, OFF by default): set the environment
  variable GATEWAY_DUMP_DIR to a folder name and every chat request is saved
  there as a JSON file -- the raw incoming messages (base64 payloads trimmed
  to a size marker) and the exact text the gateway sent to the model. It
  writes conversation text to disk: delete the folder afterwards, never
  commit it, and don't leave it switched on.

Known gaps: no allow-list of file types (Docling itself rejects what it can't read); the
Docling timeout is still a generous 300 s until measured on a long document.

Run:
    pip install fastapi uvicorn requests
    uvicorn main:app --host 0.0.0.0 --port 8000
"""

import base64
import json
import os
import re
import time
import uuid

METRICS_LOG_PATH = "gateway_metrics.jsonl"

# How problems the user can act on (bad/oversized file, chat too long, Docling
# down) reach LibreChat:
#   "http"  (default) a real HTTP error with an OpenAI-style error body, which
#           LibreChat shows in its own error box (headline + details).
#   "reply" a normal assistant message. Fallback only: it looks like the model
#           said it. Switch with the GATEWAY_ERROR_MODE environment variable.
ERROR_MODE = os.environ.get("GATEWAY_ERROR_MODE", "http").strip().lower()

# Request capture (developer option). Empty = off. Relative paths are relative
# to the folder the gateway is started from.
DUMP_DIR = os.environ.get("GATEWAY_DUMP_DIR", "").strip()

# reason -> (HTTP status, OpenAI-style error type, error code)
# 400 is on LibreChat's no-retry list, so those errors show immediately; 5xx are
# retried several times first.
ERROR_HTTP = {
    "too_long": (400, "invalid_request_error", "context_length_exceeded"),
    "bad_attachment": (400, "invalid_request_error", "invalid_attachment"),
    "unreadable_attachment": (400, "invalid_request_error", "unreadable_attachment"),
    "docling_down": (503, "server_error", "document_converter_unavailable"),
    "docling_timeout": (504, "server_error", "document_conversion_timeout"),
    "ollama_down": (503, "server_error", "service_unavailable"),
}

# Size guard. Characters per token is NOT constant. Measured here: ~5 for plain
# English, ~3-4 for OCR'd / Word text, ~1.5 for number-heavy tables. So big text
# prompts are measured exactly by Ollama (token_probe.py); the constants below
# only cover what the probe doesn't.
CHARS_PER_TOKEN = 3  # conservative fallback estimate when there is no exact count
MAX_CHARS_PER_TOKEN = 6  # most favourable ratio seen; more chars than budget*6 can't fit
PROBE_MIN_CHARS = 20_000  # below this even 1 char/token fits the budget: no probe needed
OUTPUT_RESERVE_TOKENS = 4096  # room left in the window for the model's answer

# ---- User-facing wording (plain language, no internal labels) ---------------
OLLAMA_DOWN_MESSAGE = (
    "The assistant is temporarily unavailable. Please try again in a few "
    "minutes, or contact IT support if this continues."
)
DOCLING_DOWN_MESSAGE = (
    "Reading attachments is temporarily unavailable. Please try again in a few "
    "minutes, or contact IT support if this continues."
)
DOC_TOO_LONG_MESSAGE = (
    "This document is too long for the assistant to read in one go. Please "
    "upload a shorter document, or split it into smaller parts and use a "
    "separate chat for each."
)
CHAT_TOO_LONG_MESSAGE = (
    "This conversation is too long for the assistant to handle. Please start a "
    "new chat, or shorten your message or attachment."
)


def _msg_too_many_pages(filename: str, pages: str, limit: str) -> str:
    return (
        f"'{filename}' has {pages} pages, and the limit is {limit}. Please upload "
        f"a shorter file, or split it into smaller parts and upload each one in "
        f"a new chat."
    )


def _msg_file_too_large(filename: str, limit_mb: str) -> str:
    return f"'{filename}' is too large. Please upload a file smaller than {limit_mb} MB."


def _msg_unreadable(filename: str) -> str:
    return (
        f"'{filename}' couldn't be read. It may be damaged, password-protected "
        f"or in a format that isn't supported. Please check the file and upload "
        f"it again in a new chat."
    )


def _msg_bad_upload(filename: str) -> str:
    return (
        f"We couldn't read '{filename}'. Please try uploading it again, or use "
        f"a different file."
    )


def _msg_timeout(filename: str) -> str:
    return (
        f"'{filename}' is taking longer than expected to process. Please try "
        f"again in a minute (it may have finished in the background), or upload "
        f"a shorter file."
    )


def _log_metrics(entry: dict) -> None:
    entry["timestamp"] = time.time()
    try:
        with open(METRICS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # a logging failure should never break the actual request


from docling_client import (
    CONVERT_TIMEOUT_S,
    DoclingConversionError,
    DoclingTimeoutError,
    DoclingUnavailableError,
    convert_document_ex,
    docling_is_reachable,
)
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from model_registry import MODEL_REGISTRY, ModelEntry
from ollama_client import (
    OllamaUnavailableError,
    call_model,
    get_loaded_models,
    unload_model,
)
from pydantic import BaseModel
from routing import route
from token_probe import count_prompt_tokens

app = FastAPI()

if DUMP_DIR:
    print(
        f"[dump] request capture is ON -> '{DUMP_DIR}'. Conversation text is "
        f"being written to disk; delete the folder when finished."
    )


@app.exception_handler(HTTPException)
async def openai_shaped_http_exception_handler(request: Request, exc: HTTPException):
    """LibreChat's OpenAI-compatible parser expects {"error": {"message": ...}},
    not FastAPI's default {"detail": ...} -- without this, error bodies show
    as blank/"(no body)" in the UI instead of the actual message. type/code are
    strings, as in OpenAI's own errors."""
    is_server_error = exc.status_code >= 500
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "type": "server_error" if is_server_error else "invalid_request_error",
                "code": "service_unavailable" if is_server_error else "bad_request",
            }
        },
    )


class ChatCompletionRequest(BaseModel):
    model: str | None = None  # ignored for now -- routing decides, not the caller
    messages: list[dict]
    stream: bool = False


class GatewayReply(Exception):
    """A problem the user can act on. `str(err)` is the plain-language text shown
    to the user; `detail` is the technical version, for the metrics log only.
    Returned as an HTTP error (default) or a plain assistant message (reply
    mode) by _reply_response()."""

    def __init__(self, reason: str, message: str, detail: str = ""):
        super().__init__(message)
        self.reason = reason
        self.detail = detail


def _ollama_down(e: Exception) -> GatewayReply:
    print(f"[ollama] unavailable: {e}")
    return GatewayReply("ollama_down", OLLAMA_DOWN_MESSAGE, detail=str(e))


def _trim_for_dump(obj):
    """Copy of `obj` with base64 data URLs replaced by a short size marker, so
    captured requests stay readable and small."""
    if isinstance(obj, dict):
        return {k: _trim_for_dump(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_trim_for_dump(v) for v in obj]
    if isinstance(obj, str) and obj.startswith("data:") and ";base64," in obj:
        header, payload = obj.split(",", 1)
        return f"<{header}, {len(payload):,} base64 characters trimmed>"
    return obj


def _dump_request(
    req: "ChatCompletionRequest",
    flattened: list[dict] | None,
    images: list[str] | None,
    error: str | None = None,
) -> None:
    """Save one request to GATEWAY_DUMP_DIR (no-op when the option is off).

    Keys (read by compare_pptx.py): raw = what LibreChat sent (base64 trimmed);
    final = the exact messages the gateway passes to Ollama after flattening and
    document conversion (None if the request failed before that).
    A capture failure never affects the request."""
    if not DUMP_DIR:
        return
    try:
        os.makedirs(DUMP_DIR, exist_ok=True)
        now = time.time()
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
        # Milliseconds keep file names in request order when sorted.
        name = f"{stamp}-{int((now % 1) * 1000):03d}-{uuid.uuid4().hex[:4]}.json"
        record = {
            "timestamp": now,
            "stream": req.stream,
            "requested_model": req.model,
            "raw": _trim_for_dump(req.messages),
            "final": flattened,
            "image_count": len(images or []),
            "error": error,
        }
        with open(os.path.join(DUMP_DIR, name), "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
    except Exception as e:  # capture must never break a request
        print(f"[dump] failed: {e}")


def _doc_metrics(doc_stats: dict) -> dict:
    """Metrics fields for a request's documents ({} when it has none)."""
    if not doc_stats or not doc_stats.get("count"):
        return {}
    return {
        "doc_count": doc_stats["count"],
        "doc_chars": doc_stats["chars"],
        "doc_wait_ms": round(doc_stats["wait_ms"], 1),
        "doc_convert_ms": round(doc_stats["convert_ms"], 1),
        "doc_cache_hits": doc_stats["cache_hits"],
    }


def _new_doc_stats() -> dict:
    return {"count": 0, "chars": 0, "wait_ms": 0.0, "convert_ms": 0.0, "cache_hits": 0}


_PAGES_RE = re.compile(r"Document has (\d+) pages?; the limit is (\d+)", re.IGNORECASE)
_LIMIT_MB_RE = re.compile(r"limit (\d+) MB", re.IGNORECASE)


def _conversion_failure(filename: str, e: Exception) -> GatewayReply:
    """Turn Docling's rejection into a plain-language reply. Docling's own text
    (e.g. "Document has 35 pages; the limit is 30.") is only used to pick the
    message and fill in the numbers; it is never shown to the user."""
    reason = str(e).strip()
    m = _PAGES_RE.search(reason)
    if m:
        return GatewayReply(
            "unreadable_attachment",
            _msg_too_many_pages(filename, m.group(1), m.group(2)),
            detail=reason,
        )
    if "too large" in reason.lower():
        mb = _LIMIT_MB_RE.search(reason)
        return GatewayReply(
            "unreadable_attachment",
            _msg_file_too_large(filename, mb.group(1) if mb else "25"),
            detail=reason,
        )
    return GatewayReply("unreadable_attachment", _msg_unreadable(filename), detail=reason)


def _document_block(file_obj: dict, doc_stats: dict) -> str:
    """Convert one {"type": "file"} part to a text block for the prompt."""
    filename = file_obj.get("filename") or "document"
    file_data = file_obj.get("file_data") or ""
    if not file_data.startswith("data:") or "," not in file_data:
        raise GatewayReply(
            "bad_attachment",
            _msg_bad_upload(filename),
            detail="file part has no inline base64 data",
        )
    try:
        raw = base64.b64decode(file_data.split(",", 1)[1])
    except ValueError as e:
        raise GatewayReply(
            "bad_attachment",
            _msg_bad_upload(filename),
            detail=f"base64 decode failed: {e}",
        )

    start = time.monotonic()
    try:
        converted = convert_document_ex(filename, raw)
    except DoclingUnavailableError as e:
        print(f"[docs] converter unavailable: {e}")
        raise GatewayReply("docling_down", DOCLING_DOWN_MESSAGE, detail=str(e))
    except DoclingTimeoutError as e:
        raise GatewayReply(
            "docling_timeout",
            _msg_timeout(filename),
            detail=f"no answer within {CONVERT_TIMEOUT_S} s ({e})",
        )
    except DoclingConversionError as e:
        raise _conversion_failure(filename, e)
    markdown = converted["markdown"]
    wait_ms = (time.monotonic() - start) * 1000
    doc_stats["count"] += 1
    doc_stats["chars"] += len(markdown)
    doc_stats["wait_ms"] += wait_ms
    doc_stats["convert_ms"] += converted["convert_ms"]
    doc_stats["cache_hits"] += 1 if converted["cached"] else 0
    print(
        f"[docs] {filename}: {len(markdown)} chars in {wait_ms:.0f} ms"
        f"{' (cached)' if converted['cached'] else ''}"
    )
    return (
        f"[Attached document: {filename}]\n---\n{markdown}\n---\n"
        f"[End of attached document]"
    )


def _extract_images_and_flatten(
    messages: list[dict], doc_stats: dict | None = None
) -> tuple[list[dict], list[str], bool]:
    doc_stats = doc_stats if doc_stats is not None else _new_doc_stats()
    flattened = []
    images: list[str] = []
    last_index = len(messages) - 1

    for i, msg in enumerate(messages):
        content = msg.get("content")
        if isinstance(content, str):
            flattened.append({"role": msg["role"], "content": content})
            continue

        text_parts = []
        doc_blocks = []
        for part in content or []:
            if part.get("type") == "text":
                text_parts.append(part.get("text", ""))
            elif part.get("type") == "image_url" and i == last_index:
                # Only route on an image in the newest message -- an image
                # earlier in history shouldn't pin the whole thread to vision.
                url = part.get("image_url", {}).get("url", "")
                b64_data = url.split(",", 1)[-1] if url.startswith("data:") else url
                images.append(b64_data)
            elif part.get("type") == "file":
                # Unlike images, files are converted wherever they appear in
                # the history: LibreChat resends them every turn and the model
                # needs the document in context for follow-up questions.
                doc_blocks.append(_document_block(part.get("file") or {}, doc_stats))

        text = " ".join(text_parts)
        if doc_blocks:
            # Document first, then the user's question.
            text = "\n\n".join(doc_blocks + [text])
        flattened.append({"role": msg["role"], "content": text})

    return flattened, images, bool(images)


def _check_tokens(tokens: int, model: ModelEntry, exact: bool, has_docs: bool) -> None:
    """Refuse a prompt that doesn't fit the model's context window.

    Ollama doesn't return an error for an over-long prompt, it can shorten it,
    so the model might answer without seeing part of the document and nothing
    would say so. Better to fail loudly. The user sees plain wording; the token
    numbers go to the metrics log only. `has_docs` = a document we converted is
    in the prompt (then "document", otherwise "conversation")."""
    budget = model.max_context - OUTPUT_RESERVE_TOKENS
    if tokens > budget:
        approx = "" if exact else "about "
        raise GatewayReply(
            "too_long",
            DOC_TOO_LONG_MESSAGE if has_docs else CHAT_TOO_LONG_MESSAGE,
            detail=f"{approx}{tokens:,} tokens; limit {budget:,}",
        )


def _ensure_loaded(model: ModelEntry) -> dict:
    """
    Returns which of three states occurred, since they have very different
    latency implications: already resident (fastest), cold load (gateway
    just started, nothing to evict), or an actual swap (explicit unload of
    a different Quick model before this one loads).
    """
    loaded = get_loaded_models()
    if model.ollama_tag in loaded:
        return {"action": "already_loaded", "unload_ms": 0}

    others_loaded = [
        e.ollama_tag
        for e in MODEL_REGISTRY.values()
        if e.ollama_tag in loaded and e.ollama_tag != model.ollama_tag
    ]
    if not others_loaded:
        return {"action": "cold_load", "unload_ms": 0}

    unload_start = time.monotonic()
    for tag in others_loaded:
        unload_model(tag)
    return {
        "action": "swap",
        "unload_ms": round((time.monotonic() - unload_start) * 1000, 1),
    }


def _sse_chunk(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


REPLY_MODEL_NAME = "clarisync-gateway"


def _static_sse(text: str):
    """Same two-chunk shape as a normal streamed answer, carrying `text`."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    yield _sse_chunk(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": REPLY_MODEL_NAME,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": text},
                    "finish_reason": None,
                }
            ],
        }
    )
    yield _sse_chunk(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": REPLY_MODEL_NAME,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
    )
    yield "data: [DONE]\n\n"


def _reply_response(
    err: GatewayReply, stream: bool, request_start: float, extra: dict | None = None
):
    """Report `err` to the caller (an HTTP error, or a plain reply in "reply" mode).

    The log line carries both the user text (`message`) and the technical
    version (`detail`); this log is the only place to count how often users
    hit limits, since they arrive as HTTP errors."""
    text = str(err)
    _log_metrics(
        {
            "event": "gateway_reply",
            "reason": err.reason,
            "detail": (err.detail or "")[:300],
            "message": text[:300],
            "gateway_total_ms": round((time.monotonic() - request_start) * 1000, 1),
            "stream": stream,
            **(extra or {}),
        }
    )
    if ERROR_MODE == "http":
        status, err_type, err_code = ERROR_HTTP.get(
            err.reason, (400, "invalid_request_error", err.reason)
        )
        return JSONResponse(
            status_code=status,
            content={"error": {"message": text, "type": err_type, "code": err_code}},
        )
    if stream:
        return StreamingResponse(_static_sse(text), media_type="text/event-stream")
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": REPLY_MODEL_NAME,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
    }


def _stream_response(
    model, messages, images, swap_info, request_start, has_image, prompt_chars, extra
):
    try:
        result = call_model(model, messages, images=images or None)
    except OllamaUnavailableError as e:
        # Already streaming -- can't switch to an HTTP error status now, so emit
        # the (friendly) error as a chat message instead of silently dying.
        err = _ollama_down(e)
        _log_metrics(
            {
                "event": "gateway_reply",
                "reason": err.reason,
                "detail": err.detail[:300],
                "message": str(err),
                "gateway_total_ms": round((time.monotonic() - request_start) * 1000, 1),
                "stream": True,
                **extra,
            }
        )
        yield _sse_chunk(
            {
                "id": f"chatcmpl-{uuid.uuid4().hex}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model.ollama_tag,
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "content": OLLAMA_DOWN_MESSAGE,
                        },
                        "finish_reason": "stop",
                    }
                ],
            }
        )
        yield "data: [DONE]\n\n"
        return
    _log_metrics(
        {
            "model": model.ollama_tag,
            "has_image": has_image,
            "swap_action": swap_info["action"],
            "unload_ms": swap_info["unload_ms"],
            "ollama_load_ms": result["load_duration_ms"],
            "ollama_total_ms": result["total_duration_ms"],
            "gateway_total_ms": round((time.monotonic() - request_start) * 1000, 1),
            "prompt_chars": prompt_chars,
            "prompt_tokens": result["raw"].get("prompt_eval_count"),
            "stream": True,
            **extra,
        }
    )
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    yield _sse_chunk(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model.ollama_tag,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": result["content"]},
                    "finish_reason": None,
                }
            ],
        }
    )
    yield _sse_chunk(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model.ollama_tag,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
    )
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
def chat_completions(req: ChatCompletionRequest):
    request_start = time.monotonic()
    doc_stats = _new_doc_stats()
    messages: list[dict] | None = None
    images: list[str] = []
    dumped = False
    extra: dict = {}
    try:
        messages, images, has_image = _extract_images_and_flatten(
            req.messages, doc_stats
        )
        _dump_request(req, messages, images)
        dumped = True
        has_docs = doc_stats["count"] > 0
        model = route(messages, has_image)
        print(f"[routing] has_image={has_image} -> {model.ollama_tag}")

        prompt_chars = sum(len(m["content"]) for m in messages)
        # Big text prompts get an exact count from Ollama below; here we only
        # refuse what cannot possibly fit, before any model is loaded. Small
        # prompts and image requests keep the conservative estimate.
        use_probe = (not images) and prompt_chars > PROBE_MIN_CHARS
        ratio = MAX_CHARS_PER_TOKEN if use_probe else CHARS_PER_TOKEN
        _check_tokens(prompt_chars // ratio, model, exact=False, has_docs=has_docs)

        try:
            swap_info = _ensure_loaded(model)
        except OllamaUnavailableError as e:
            raise _ollama_down(e)

        extra = _doc_metrics(doc_stats)
        if use_probe:
            probe_start = time.monotonic()
            try:
                exact_tokens = count_prompt_tokens(model, messages)
            except OllamaUnavailableError as e:
                raise _ollama_down(e)
            extra["probe_tokens"] = exact_tokens
            extra["probe_ms"] = round((time.monotonic() - probe_start) * 1000, 1)
            if exact_tokens:
                _check_tokens(exact_tokens, model, exact=True, has_docs=has_docs)
            else:  # Ollama gave no count: fall back to the conservative estimate
                _check_tokens(
                    prompt_chars // CHARS_PER_TOKEN,
                    model,
                    exact=False,
                    has_docs=has_docs,
                )
    except GatewayReply as err:
        if not dumped:  # failed while reading the attachments: capture what came in
            _dump_request(req, None, images, error=err.reason)
        return _reply_response(
            err, req.stream, request_start, extra or _doc_metrics(doc_stats)
        )

    if req.stream:
        return StreamingResponse(
            _stream_response(
                model,
                messages,
                images,
                swap_info,
                request_start,
                has_image,
                prompt_chars,
                extra,
            ),
            media_type="text/event-stream",
        )

    try:
        result = call_model(model, messages, images=images or None)
    except OllamaUnavailableError as e:
        return _reply_response(_ollama_down(e), False, request_start, extra)
    _log_metrics(
        {
            "model": model.ollama_tag,
            "has_image": has_image,
            "swap_action": swap_info["action"],
            "unload_ms": swap_info["unload_ms"],
            "ollama_load_ms": result["load_duration_ms"],
            "ollama_total_ms": result["total_duration_ms"],
            "gateway_total_ms": round((time.monotonic() - request_start) * 1000, 1),
            "prompt_chars": prompt_chars,
            "prompt_tokens": result["raw"].get("prompt_eval_count"),
            "stream": False,
            **extra,
        }
    )
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model.ollama_tag,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result["content"]},
                "finish_reason": "stop",
            }
        ],
    }


@app.get("/health")
def health():
    """Reports whether the gateway can actually reach Ollama, not just
    whether the gateway process itself is up -- reuses get_loaded_models()
    since it's already the lightweight, fast reachability check.

    Ollama down -> 503 (nothing works). Docling down -> still HTTP 200 but
    status "degraded": plain chat keeps working, only document uploads fail
    (with their own clear 503), so this shouldn't take the gateway out of
    rotation."""
    docling_ok = docling_is_reachable()
    try:
        get_loaded_models()
    except OllamaUnavailableError as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "ollama_reachable": False,
                "docling_reachable": docling_ok,
                "detail": str(e),
            },
        )
    return {
        "status": "ok" if docling_ok else "degraded",
        "ollama_reachable": True,
        "docling_reachable": docling_ok,
    }