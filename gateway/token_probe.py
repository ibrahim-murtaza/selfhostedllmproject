"""
Exact prompt size, measured by the model's own tokenizer.

Why this exists: characters-per-token is not constant. Measured on this
gateway: about 5 for plain English prose, 3-4 for OCR'd or Word text, and
about 1.5 for number-heavy tables (digits are tokenised one by one). Any fixed
ratio is either too strict for prose or too lenient for tables, and a
too-lenient guard means Ollama silently shortens the prompt.

How: send the same request with num_predict=1 (generate a single token) and
read Ollama's own prompt_eval_count. The work isn't wasted: Ollama keeps the
prompt in its KV cache, so the real request that follows re-uses it (a 15k
token follow-up turn was measured at ~0.6 s total).

Only used for big text prompts (see PROBE_MIN_CHARS in main.py).
"""

import requests

from model_registry import ModelEntry
from ollama_client import OLLAMA_BASE_URL, TIMEOUT_SECONDS, OllamaUnavailableError


def count_prompt_tokens(model: ModelEntry, messages: list[dict]) -> int | None:
    """Return Ollama's prompt token count for `messages`, or None if Ollama
    didn't report one (the caller then falls back to an estimate)."""
    payload = {
        "model": model.ollama_tag,
        "messages": messages,
        "stream": False,
        "think": False,  # same as the real text call, so the cached prompt matches
        "options": {"num_predict": 1},
    }
    if model.context_placement == "request":
        payload["options"]["num_ctx"] = model.max_context
    # else "modelfile" placement -- num_ctx is already baked in, don't override.

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=TIMEOUT_SECONDS
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise OllamaUnavailableError("Cannot reach Ollama -- is it running?")
    except requests.exceptions.Timeout:
        raise OllamaUnavailableError(f"Ollama did not respond within {TIMEOUT_SECONDS}s.")
    except requests.exceptions.HTTPError as e:
        raise OllamaUnavailableError(f"Ollama returned an error: {e}")

    return resp.json().get("prompt_eval_count") or None