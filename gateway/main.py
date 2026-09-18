"""
FastAPI gateway -- OpenAI-compatible /v1/chat/completions endpoint that
LibreChat calls instead of hitting Ollama directly.

Scope of this skeleton:
- Non-streaming only (stream:false), matching everything validated in
  testing so far. Streaming is a known gap, not yet built.
- Swap orchestration: explicitly unloads any other resident Quick model
  before loading a new one (deterministic, not relying on Ollama's
  idle-timeout auto-eviction -- see handoff note on why).
- Routing: Stage 1 (image-attached -> vision) is real; Stages 2-4 are
  no-ops (see routing.py) since only one text tier exists.

Run:
    pip install fastapi uvicorn requests
    uvicorn main:app --host 0.0.0.0 --port 8000
"""

import time
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from model_registry import MODEL_REGISTRY, ModelEntry
from ollama_client import call_model, get_loaded_models, unload_model
from routing import route

app = FastAPI()


class ChatCompletionRequest(BaseModel):
    model: str | None = None  # ignored for now -- routing decides, not the caller
    messages: list[dict]
    stream: bool = False


def _extract_images_and_flatten(messages: list[dict]) -> tuple[list[dict], list[str], bool]:
    """
    Convert OpenAI-style multi-part message content (text + image_url parts)
    into Ollama's shape: plain string content per message, images as a
    separate base64 list. Returns (flattened_messages, images, has_image).
    """
    flattened = []
    images: list[str] = []
    has_image = False

    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            flattened.append({"role": msg["role"], "content": content})
            continue

        text_parts = []
        for part in content or []:
            if part.get("type") == "text":
                text_parts.append(part.get("text", ""))
            elif part.get("type") == "image_url":
                has_image = True
                url = part.get("image_url", {}).get("url", "")
                # Strip "data:image/png;base64," prefix if present.
                b64_data = url.split(",", 1)[-1] if url.startswith("data:") else url
                images.append(b64_data)

        flattened.append({"role": msg["role"], "content": " ".join(text_parts)})

    return flattened, images, has_image


def _ensure_loaded(model: ModelEntry) -> None:
    """
    Swap orchestration: if the target model isn't already resident,
    explicitly unload any other Quick-tier model that is, before the
    upcoming call_model() triggers Ollama's auto-load. VRAM is tight
    enough (12GB) that waiting on the default 5-minute idle-timeout evict
    risks an OOM instead of a clean swap.
    """
    loaded = get_loaded_models()
    if model.ollama_tag in loaded:
        return  # already resident, nothing to do

    for entry in MODEL_REGISTRY.values():
        if entry.ollama_tag in loaded and entry.ollama_tag != model.ollama_tag:
            unload_model(entry.ollama_tag)


@app.post("/v1/chat/completions")
def chat_completions(req: ChatCompletionRequest):
    if req.stream:
        raise HTTPException(status_code=400, detail="Streaming not yet supported by this gateway.")

    messages, images, has_image = _extract_images_and_flatten(req.messages)
    model = route(messages, has_image)
    _ensure_loaded(model)

    result = call_model(model, messages, images=images or None)

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
    return {"status": "ok"}
