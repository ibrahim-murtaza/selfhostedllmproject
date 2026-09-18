"""
Ollama client -- thin wrapper around Ollama's native /api/chat, /api/ps,
and /api/generate endpoints. Mirrors the request shape already validated
by test_runner.py and vision_test_runner.py, so gateway behavior matches
what was actually tested rather than diverging into something new.
"""

import requests

from model_registry import ModelEntry

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
TIMEOUT_SECONDS = 180

class OllamaUnavailableError(Exception):
    """Raised when Ollama can't be reached or times out -- lets main.py
    return a clean error instead of a raw 500 with a stack trace."""
    pass

def get_loaded_models() -> set[str]:
    """Return the set of Ollama model tags currently resident in VRAM."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/ps", timeout=10)
        resp.raise_for_status()
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        raise OllamaUnavailableError("Cannot reach Ollama -- is it running?")
    except requests.exceptions.HTTPError as e:
        raise OllamaUnavailableError(f"Ollama returned an error: {e}")
    return {m["name"] for m in resp.json().get("models", [])}


def unload_model(ollama_tag: str) -> None:
    """
    Force-unload a model immediately (keep_alive: 0), rather than waiting
    for Ollama's default 5-minute idle timeout to release VRAM. Used by
    swap orchestration in main.py before loading a different Quick model --
    see the explicit-unload-vs-auto-evict note in the handoff.
    """
    try:
        requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": ollama_tag, "keep_alive": 0},
            timeout=30,
        )
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        raise OllamaUnavailableError("Cannot reach Ollama -- is it running?")


def call_model(
    model: ModelEntry,
    messages: list[dict],
    images: list[str] | None = None,
) -> dict:
    """
    Call Ollama's /api/chat for the given registry entry.

    - Text models: think:false is forced, matching test_runner.py's
      validated behavior (the Quick text model reasons by default even on
      trivial prompts -- a real latency cost, confirmed in KV-cache
      measurement work; forcing it off is deliberate, not an oversight).
    - Vision models: think is left unset (model decides), and output is
      recovered from the 'thinking' field if 'content' comes back empty --
      matches vision_test_runner.py's known-issue handling (Ollama issue
      #14716 for Qwen3.5; Gemma4/Ministral3 may also route there under
      heavy reasoning).
    """
    payload = {
        "model": model.ollama_tag,
        "messages": messages,
        "stream": False,
    }

    if images:
        payload["messages"][-1]["images"] = images
    else:
        payload["think"] = False

    if model.context_placement == "request":
        payload["options"] = {"num_ctx": model.max_context}
    # else "modelfile" placement -- num_ctx is already baked in, don't override.

    try:
        resp = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise OllamaUnavailableError("Cannot reach Ollama -- is it running?")
    except requests.exceptions.Timeout:
        raise OllamaUnavailableError(f"Ollama did not respond within {TIMEOUT_SECONDS}s.")
    except requests.exceptions.HTTPError as e:
        raise OllamaUnavailableError(f"Ollama returned an error: {e}")
    data = resp.json()

    content = data["message"].get("content", "").strip()
    thinking = data["message"].get("thinking", "").strip()
    recovered = False
    if not content and thinking:
        content = thinking
        recovered = True

    # Ollama reports its own timing in nanoseconds when stream:false -- more
    # precise than wrapping the request in our own wall-clock timer, and
    # load_duration specifically isolates the cost of a cold/swapped-in model.
    def _ns_to_ms(key: str) -> float:
        return round(data.get(key, 0) / 1_000_000, 1)

    return {
        "content": content,
        "recovered_from_thinking": recovered,
        "raw": data,
        "total_duration_ms": _ns_to_ms("total_duration"),
        "load_duration_ms": _ns_to_ms("load_duration"),
        "prompt_eval_duration_ms": _ns_to_ms("prompt_eval_duration"),
        "eval_duration_ms": _ns_to_ms("eval_duration"),
    }
