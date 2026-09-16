"""
Quick-tier vision testing.

Sends test images to the vision-capable Quick candidates, saves raw output
per model. No automated scoring — same as the text runner, quality judgment
happens externally (Claude can compare output directly against the source
image once both are shared).

Unlike the text runner, this does NOT force think:false. Image tasks are a
genuine capability question (reading a messy scan, interpreting a cluttered
screenshot), not pure overhead like translating a clean sentence — so each
model is left free to reason if it wants to.

Known issue handled here: Qwen3.5 always routes vision output into the
'thinking' field instead of 'content', regardless of any think setting
(Ollama issue #14716 — the toggle has no effect on image calls for this
model). Gemma4/Ministral3 may also route to 'thinking' if they reason
heavily. This script recovers whichever field actually has the answer and
tags it, so it reads as a known behavior, not a mystery blank.

Requires Ollama running locally and the `requests` package:
    pip install requests

Run:
    python vision_test_runner.py
"""

import base64
import csv
import datetime
import re
import time

import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
TIMEOUT_SECONDS = 180

# ---------------------------------------------------------------------------
# DATA — edit this section: models, image paths, prompts, repeat counts
# ---------------------------------------------------------------------------

MODELS = [
    "quick-gemma4-12b",
    "quick-qwen3.5-9b",
    "quick-ministral3-8b",
]

DEFAULT_REPEATS = 3  # lower than text tests — each image is a fixed input,
                      # repeats here check consistency, not prompt variety

# Fill in real paths once images are sourced. One entry per test image.
IMAGE_TESTS = [
    {
        "name": "email_screenshot",
        "image_path": "images/email_screenshot.png",
        "prompt": "Summarize this email and draft a one-line reply.",
        "repeats": DEFAULT_REPEATS,
    },
    {
        "name": "handwritten_notes",
        "image_path": "images/whiteboard_notes.png",
        "prompt": "Turn the handwritten notes in this image into a bulleted list of meeting notes.",
        "repeats": DEFAULT_REPEATS,
    },
    {
        "name": "bug_screenshot",
        "image_path": "images/bug_dialog.png",
        "prompt": "Write a bug report describing what's shown in this screenshot.",
        "repeats": DEFAULT_REPEATS,
    },
    {
        "name": "invoice_photo",
        "image_path": "images/invoice.png",
        "prompt": "Categorize this as a support ticket type based on what's shown.",
        "repeats": DEFAULT_REPEATS,
    },
    {
        "name": "degraded_scan",
        "image_path": "images/scanned_doc.png",
        "prompt": "Transcribe the text visible in this document.",
        "repeats": DEFAULT_REPEATS,
    },
    {
        "name": "chart_screenshot",
        "image_path": "images/chart.png",
        "prompt": "Summarize what this chart shows in one or two sentences.",
        "repeats": DEFAULT_REPEATS,
    },
]

# ---------------------------------------------------------------------------


def safe_filename(model):
    return re.sub(r"[^a-zA-Z0-9._-]", "-", model)


def encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def call_ollama_vision(model, prompt, image_b64):
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "messages": [
                {"role": "user", "content": prompt, "images": [image_b64]}
            ],
            # No think:false here, unlike the text runner. Image tasks are
            # a real capability question, not pure overhead — let each
            # model reason if it wants to. (Also moot for Qwen3.5: the
            # toggle has no effect on image calls either way, per Ollama
            # issue #14716 — content is always empty there regardless.)
            "stream": False,
        },
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    data = resp.json()
    content = data["message"].get("content", "").strip()
    thinking = data["message"].get("thinking", "").strip()

    # Fallback stays regardless of the think setting: Qwen3.5 always routes
    # image output to thinking, and Gemma4/Ministral3 may too if they
    # reason heavily. Recover whichever field actually has the answer.
    recovered = False
    if not content and thinking:
        content = thinking
        recovered = True

    return content, recovered


def run():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = f"vision_results_summary_{timestamp}.csv"
    summary_rows = []
    raw_paths = []

    overall_start = time.monotonic()

    for model in MODELS:
        raw_path = f"vision_results_raw_{safe_filename(model)}_{timestamp}.md"
        raw_paths.append(raw_path)
        print(f"\n=== {model} ===")
        model_start = time.monotonic()
        error_count = 0
        routed_to_thinking_count = 0

        with open(raw_path, "w", encoding="utf-8") as raw_file:
            raw_file.write(f"# {model}\n\n")

            for test in IMAGE_TESTS:
                raw_file.write(f"## {test['name']}\n\n")
                print(f"-- {test['name']} ({test['repeats']} runs) --")

                try:
                    image_b64 = encode_image(test["image_path"])
                except FileNotFoundError:
                    msg = f"[SKIPPED: image not found at {test['image_path']}]"
                    raw_file.write(f"{msg}\n\n---\n\n")
                    print(f"  {msg}")
                    continue

                for i in range(test["repeats"]):
                    try:
                        content, recovered = call_ollama_vision(
                            model, test["prompt"], image_b64
                        )
                        status = "ok (recovered from thinking)" if recovered else "ok"
                        if recovered:
                            routed_to_thinking_count += 1
                    except Exception as e:
                        content = f"[ERROR: {e}]"
                        recovered = False
                        status = "ERROR"
                        error_count += 1

                    tag = (
                        " *(recovered from thinking field — skim before "
                        "trusting as a clean final answer)*"
                        if recovered else ""
                    )
                    raw_file.write(f"### Run {i + 1}{tag}\n\n{content}\n\n")
                    print(f"  run {i + 1}: {status}")

                raw_file.write("---\n\n")

        model_elapsed = time.monotonic() - model_start
        summary_rows.append(
            {
                "model": model,
                "errors": error_count,
                "routed_to_thinking": routed_to_thinking_count,
                "minutes": round(model_elapsed / 60, 1),
            }
        )
        print(f"  ({model_elapsed / 60:.1f} min, {error_count} errors, "
              f"{routed_to_thinking_count} routed-to-thinking)")

    overall_elapsed = time.monotonic() - overall_start

    with open(summary_path, "w", newline="", encoding="utf-8") as summary_file:
        writer = csv.DictWriter(
            summary_file,
            fieldnames=["model", "errors", "routed_to_thinking", "minutes"],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    print("\nRaw output written to:")
    for p in raw_paths:
        print(f"  {p}")
    print(f"Summary written to: {summary_path}")
    print(f"Total time: {overall_elapsed / 60:.1f} minutes")


if __name__ == "__main__":
    run()