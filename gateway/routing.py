"""
Routing cascade -- cheapest-check-first, to minimize classification
latency and GPU model swaps.

Stage 1 (content-type check) is real and active: with only one text tier
built, it's the only stage with anything to route between.

Stages 2-4 are scaffolded as inert no-ops. They activate once a second
text tier (General/Deep) exists -- there's currently nothing for
keyword/embedding/router-LLM disambiguation to choose between.
"""

from model_registry import ModelEntry, get_model


def route(messages: list[dict], has_image: bool) -> ModelEntry:
    # Stage 1 -- content-type check (free, instant)
    if has_image:
        return get_model("quick-vision")

    # Stage 2 -- regex/keyword match against known task categories (no-op)
    # Stage 3 -- embedding-similarity fallback (no-op)
    # Stage 4 -- small resident router LLM, last resort (no-op)
    # Only one text tier exists right now, so every non-image request
    # routes here regardless of content.
    return get_model("quick-text")
