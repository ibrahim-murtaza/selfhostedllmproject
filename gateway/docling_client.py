"""
Client for the local Docling conversion service (docling_service/main.py).

convert_document(filename, data)     -> markdown text
convert_document_ex(filename, data)  -> {"markdown", "cached", "convert_ms"}
                                        (what the gateway uses, for metrics)

Raises:
    DoclingUnavailableError  service unreachable
    DoclingTimeoutError      service reachable but the conversion took longer
                             than CONVERT_TIMEOUT_S (it keeps working and caches
                             the result, so a retry can succeed)
    DoclingConversionError   service reachable but rejected the file

127.0.0.1 rather than "localhost" on purpose: on this machine "localhost"
added a fixed ~4s per request (see Ollama client notes).
"""

import os

import requests

DOCLING_BASE_URL = "http://127.0.0.1:8001"
# Measured: ~10-12 s for 3-12 page text PDFs on CPU. Generous until a real
# 25-30 page document has been timed.
CONVERT_TIMEOUT_S = 300


class DoclingUnavailableError(Exception):
    pass


class DoclingTimeoutError(Exception):
    pass


class DoclingConversionError(Exception):
    pass


def _ascii_filename(filename: str) -> str:
    # HTTP headers must be latin-1 safe; Docling only needs the extension to
    # pick a format, so keep the extension and strip the rest to ASCII.
    stem, ext = os.path.splitext(filename or "")
    stem = stem.encode("ascii", "ignore").decode() or "document"
    ext = ext.encode("ascii", "ignore").decode()
    return stem + ext


def convert_document(filename: str, data: bytes) -> str:
    return convert_document_ex(filename, data)["markdown"]


def convert_document_ex(filename: str, data: bytes) -> dict:
    try:
        resp = requests.post(
            f"{DOCLING_BASE_URL}/convert",
            data=data,
            headers={
                "X-Filename": _ascii_filename(filename),
                "Content-Type": "application/octet-stream",
            },
            timeout=CONVERT_TIMEOUT_S,
        )
    except requests.ConnectionError as e:  # includes ConnectTimeout
        raise DoclingUnavailableError(
            "Cannot reach the document converter -- is the Docling service running?"
        ) from e
    except requests.Timeout as e:  # connected, but no answer in time
        raise DoclingTimeoutError(
            f"Conversion did not finish within {CONVERT_TIMEOUT_S} s."
        ) from e

    if resp.status_code == 200:
        body = resp.json()
        return {
            "markdown": body["markdown"],
            "cached": bool(body.get("cached", False)),
            "convert_ms": float(body.get("convert_ms", 0.0)),
        }

    try:
        message = resp.json()["error"]["message"]
    except Exception:
        message = resp.text[:200] or f"HTTP {resp.status_code}"
    raise DoclingConversionError(message)


def docling_is_reachable() -> bool:
    """Lightweight check used by the gateway's /health."""
    try:
        return requests.get(f"{DOCLING_BASE_URL}/health", timeout=3).status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False