"""
Quick-tier testing regime prompt runner.

Calls each Quick-tier candidate model N times per test prompt, and saves the
raw output per model for manual review. No automated scoring — quality
judgment happens externally, not via keyword matching.

Requires Ollama running locally (default http://localhost:11434) and the
`requests` package:
    pip install requests

Run:
    python test_runner.py
"""

import csv
import datetime
import re
import time

import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
TIMEOUT_SECONDS = 180

# ---------------------------------------------------------------------------
# DATA — edit this section to add/remove models, prompts, or repeat counts
# ---------------------------------------------------------------------------

MODELS = [
    "quick-mistral-7b",
    "quick-qwen3.5-9b",
    "quick-gemma4-12b",
    "quick-ministral3-8b",
    "quick-qwen3-8b",
    "quick-llama3.1-8b",
]

# Default repeat count for most tests. Override per-test below where needed.
DEFAULT_REPEATS = 10

TESTS = [
    {
        "name": "proofreading",
        "prompt": "Proofread this: 'We recieve the shipment on tuesday, however there was three "
        "boxes missing and we havent recieved a explanation yet.'",
        "repeats": 15,
    },
    {
        "name": "translation",
        "prompt": "Translate this to Spanish: 'Thank you for your order. It will ship within two "
        "business days.'",
        "repeats": DEFAULT_REPEATS,
    },
    {
        "name": "meeting_notes",
        "prompt": "Turn this into meeting notes: we talked about the Q3 budget, marketing wants "
        "more spend on ads, finance pushed back, we agreed to revisit in two weeks, "
        "Sarah is following up with vendor pricing before then.",
        "repeats": DEFAULT_REPEATS,
    },
    {
        "name": "customer_reply",
        "prompt": "Customer emailed saying their invoice shows double charges for last month. "
        "Draft a reply acknowledging it and letting them know we're looking into it.",
        "repeats": DEFAULT_REPEATS,
    },
    {
        "name": "scheduling",
        "prompt": "Draft a message to reschedule tomorrow's 2pm sync to Thursday same time, one "
        "attendee has a conflict.",
        "repeats": DEFAULT_REPEATS,
    },
    {
        "name": "job_description",
        "prompt": "Write a short job description for a Junior QA Analyst role, entry level, "
        "on-site.",
        "repeats": DEFAULT_REPEATS,
    },
    {
        "name": "vendor_communication",
        "prompt": "Draft a message to a vendor letting them know their last shipment was delayed "
        "and asking for an updated delivery estimate.",
        "repeats": DEFAULT_REPEATS,
    },
    {
        "name": "bug_report",
        "prompt": "Write a bug report: clicking 'Export to PDF' on the reports page does nothing, "
        "no error message shown, happens every time, tested on Chrome.",
        "repeats": DEFAULT_REPEATS,
    },
    {
        "name": "ticket_triage",
        "prompt": "Categorize this support ticket: 'My invoice shows the wrong billing address, "
        "can someone fix this?'",
        "repeats": DEFAULT_REPEATS,
    },
    {
        "name": "faq_entry",
        "prompt": "Write a short FAQ entry answering: 'How do I reset my password?'",
        "repeats": DEFAULT_REPEATS,
    },
    {
        "name": "internal_email",
        "prompt": "Draft an email to the team letting them know the office will be closed next "
        "Monday for a public holiday.",
        "repeats": DEFAULT_REPEATS,
    },
]

# ---------------------------------------------------------------------------


def safe_filename(model):
    """Make a model tag like 'qwen3.5:9b' safe for use in a filename."""
    return re.sub(r"[^a-zA-Z0-9._-]", "-", model)


def call_ollama(model, prompt):
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "think": False,
            "stream": False,
        },
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def run():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = f"results_summary_{timestamp}.csv"
    summary_rows = []
    raw_paths = []

    overall_start = time.monotonic()

    for model in MODELS:
        raw_path = f"results_raw_{safe_filename(model)}_{timestamp}.md"
        raw_paths.append(raw_path)
        print(f"\n=== {model} ===")
        model_start = time.monotonic()
        error_count = 0

        with open(raw_path, "w", encoding="utf-8") as raw_file:
            raw_file.write(f"# {model}\n\n")

            for test in TESTS:
                raw_file.write(f"## {test['name']}\n\n")
                print(f"-- {test['name']} ({test['repeats']} runs) --")

                for i in range(test["repeats"]):
                    try:
                        output = call_ollama(model, test["prompt"])
                        status = "ok"
                    except Exception as e:
                        output = f"[ERROR: {e}]"
                        status = "ERROR"
                        error_count += 1

                    raw_file.write(f"### Run {i + 1}\n\n{output}\n\n")
                    print(f"  run {i + 1}: {status}")

                raw_file.write("---\n\n")

        model_elapsed = time.monotonic() - model_start
        total_calls = sum(t["repeats"] for t in TESTS)
        summary_rows.append(
            {
                "model": model,
                "total_calls": total_calls,
                "errors": error_count,
                "minutes": round(model_elapsed / 60, 1),
            }
        )
        print(f"  ({model_elapsed / 60:.1f} min, {error_count} errors)")

    overall_elapsed = time.monotonic() - overall_start

    with open(summary_path, "w", newline="", encoding="utf-8") as summary_file:
        writer = csv.DictWriter(
            summary_file, fieldnames=["model", "total_calls", "errors", "minutes"]
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    print("\nRaw output written to:")
    for p in raw_paths:
        print(f"  {p}")
    print(
        f"Summary (call counts/timing/errors, not scoring) written to: {summary_path}"
    )
    print(f"Total time: {overall_elapsed / 60:.1f} minutes")


if __name__ == "__main__":
    run()
