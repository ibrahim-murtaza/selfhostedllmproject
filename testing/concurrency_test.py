"""Concurrency test for the Clarisync gateway (text only, stdlib only).

Fires N streaming chat requests at the same moment and reports, per request,
time to first token (ttft) and total time. Optionally cancels one request
mid-stream (like the UI Stop button) to check the others are unaffected.

Usage (from the prod repo, any Python 3):
    python testing\\concurrency_test.py                 # 3 simultaneous requests
    python testing\\concurrency_test.py -n 5            # 5 simultaneous requests
    python testing\\concurrency_test.py -n 3 --stop 0   # request #0 is cancelled after 3 s
    python testing\\concurrency_test.py --rounds 3      # repeat the burst 3 times

Side window while it runs:  nvidia-smi -l 1
Before/after:               ollama ps
"""
import argparse
import http.client
import json
import socket
import statistics
import threading
import time
from urllib.parse import urlparse

PROMPTS = [
    "Write a 300-word onboarding guide for a new finance analyst.",
    "Explain how a purchase order differs from an invoice, with a short example. About 300 words.",
    "Draft a 300-word internal announcement about a scheduled system maintenance window.",
    "Describe, in about 300 words, how to prepare for a quarterly budget review meeting.",
    "Write a 300-word summary of good practices for handling confidential documents.",
]


def one_request(idx, base, model, api_key, max_tokens, stop_after, barrier, results):
    u = urlparse(base)
    body = json.dumps({
        "model": model,
        "stream": True,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": PROMPTS[idx % len(PROMPTS)]}],
    })
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    r = {"idx": idx, "ttft": None, "total": None, "chars": 0, "chunks": 0,
         "status": None, "error": None, "cancelled": False}
    results[idx] = r
    conn = None
    timer = None
    barrier.wait()
    t0 = time.perf_counter()
    try:
        conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=300)
        conn.connect()
        if stop_after is not None:
            def cancel():  # like the UI Stop button: drop the connection, even while queued
                r["cancelled"] = True
                try:
                    conn.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                conn.sock.close()
            timer = threading.Timer(stop_after, cancel)
            timer.start()
        conn.request("POST", u.path.rstrip("/") + "/chat/completions", body, headers)
        resp = conn.getresponse()
        r["status"] = resp.status
        if resp.status != 200:
            r["error"] = resp.read(300).decode("utf-8", "replace")
            return
        while True:
            line = resp.readline()
            if not line:
                break
            line = line.strip()
            if not line.startswith(b"data:"):
                continue
            payload = line[5:].strip()
            if payload == b"[DONE]":
                break
            try:
                obj = json.loads(payload)
            except ValueError:
                continue
            piece = ""
            for ch in obj.get("choices", []):
                piece += (ch.get("delta") or {}).get("content") or ""
            if piece:
                if r["ttft"] is None:
                    r["ttft"] = time.perf_counter() - t0
                r["chars"] += len(piece)
                r["chunks"] += 1
    except Exception as e:  # noqa: BLE001
        if not r["cancelled"]:
            r["error"] = repr(e)
    finally:
        if timer is not None:
            timer.cancel()
        r["total"] = time.perf_counter() - t0
        if conn is not None:
            conn.close()


def run_round(args, round_no):
    barrier = threading.Barrier(args.n)
    results = {}
    threads = []
    for i in range(args.n):
        stop_after = args.stop_at if args.stop == i else None
        t = threading.Thread(target=one_request, args=(
            i, args.base, args.model, args.api_key, args.max_tokens,
            stop_after, barrier, results))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    print(f"\n=== round {round_no} | {args.n} simultaneous | model {args.model} ===")
    print(f"{'#':>2} {'status':>6} {'ttft_s':>7} {'total_s':>8} {'chars':>6} {'chunks':>6}  note")
    for i in range(args.n):
        r = results[i]
        note = "cancelled at 3 s (Stop test)" if r["cancelled"] else (r["error"] or "")
        ttft = f"{r['ttft']:.2f}" if r["ttft"] is not None else "-"
        tot = f"{r['total']:.2f}" if r["total"] is not None else "-"
        print(f"{i:>2} {str(r['status']):>6} {ttft:>7} {tot:>8} {r['chars']:>6} {r['chunks']:>6}  {note}")
    done = [r for r in results.values() if r["ttft"] is not None and not r["cancelled"]]
    if done:
        tt = [r["ttft"] for r in done]
        to = [r["total"] for r in done]
        print(f"ttft  min {min(tt):.2f}  median {statistics.median(tt):.2f}  max {max(tt):.2f}")
        print(f"total min {min(to):.2f}  median {statistics.median(to):.2f}  max {max(to):.2f}"
              f"  (spread first->last finisher {max(to) - min(to):.2f} s)")
    return list(results.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=3, help="simultaneous requests")
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--base", default="http://127.0.0.1:8000/v1")
    ap.add_argument("--model", default="quick-text")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--max-tokens", type=int, default=500)
    ap.add_argument("--stop", type=int, default=None,
                    help="index of one request to cancel")
    ap.add_argument("--stop-at", type=float, default=3.0,
                    help="seconds before the cancelled request is dropped")
    ap.add_argument("--out", default="", help="optional path to save raw results as JSON")
    args = ap.parse_args()

    allres = []
    for k in range(1, args.rounds + 1):
        allres.append(run_round(args, k))
        if k < args.rounds:
            time.sleep(5)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(allres, f, indent=2)
        print("saved", args.out)


if __name__ == "__main__":
    main()