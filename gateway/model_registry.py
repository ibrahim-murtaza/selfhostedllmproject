"""
Model registry -- single source of truth for which models exist, their
capability, tier, and context configuration. Adding or swapping a model
is a data change here, not a code change elsewhere in the gateway.

Only Quick tier is populated: General and Deep are out of scope for this
phase (don't fit in 12GB regardless -- ~13GB and ~19.5GB weights alone).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelEntry:
    ollama_tag: str          # exact name passed to Ollama's /api/chat "model" field
    tier: str                # "quick" | "general" | "deep" (only "quick" populated so far)
    capability: str          # "text" | "vision" | "text+vision"
    max_context: int         # locked context window for this model
    context_placement: str   # "modelfile" (num_ctx baked in) | "request" (send options.num_ctx per call)
    default_load: bool       # True if this model should be resident at gateway startup


MODEL_REGISTRY: dict[str, ModelEntry] = {
    "quick-text": ModelEntry(
        ollama_tag="quick-qwen3-8b:latest",
        tier="quick",
        capability="text",
        max_context=32768,       # locked via A.4 quantization + context validation
        context_placement="modelfile",
        default_load=True,
    ),
    "quick-vision": ModelEntry(
        ollama_tag="quick-ministral3-8b:latest",
        tier="quick",
        capability="vision",
        max_context=8192,        # kept at default -- context-extension test was
                                  # inconclusive, no evidence 16384 was needed
        context_placement="modelfile",
        default_load=False,      # swaps in on image upload only
    ),
}


def get_model(role: str) -> ModelEntry:
    """Look up a registry entry by role key (e.g. 'quick-text')."""
    if role not in MODEL_REGISTRY:
        raise KeyError(f"Unknown model role: {role!r}. Known roles: {list(MODEL_REGISTRY)}")
    return MODEL_REGISTRY[role]
