r"""Pilot metrics summary for gateway_metrics.jsonl (stdlib only, read-only).

Run from the repo root:
    python testing\metrics_summary.py
    python testing\metrics_summary.py --since 2026-10-05
    python testing\metrics_summary.py path\to\gateway_metrics.jsonl

--since takes a UTC date (YYYY-MM-DD) or a Unix timestamp. Use it to drop the
test traffic and look only at the pilot window.
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

# client_cancelled rows older than this are pre-Stop-fix junk (flushed at the
# gateway restart on 1 Oct); exclude them from analysis.
JUNK_BEFORE = 1790840500
QUEUED_TTFT_MS = 1500  # already-loaded text turn slower than this = waited in queue
CONVERT_LIMIT_MS = 300_000
BUSY_PCT = 30  # same thresholds as the GPU watcher
IDLE_PCT = 10
HIGH_PCT = 90
SAMPLE_GAP_S = 45  # logger samples every 30 s; a longer gap means it was off
GPU_CANDIDATES = [
    os.path.join("logs", "gpu_metrics.csv"),
    "gpu_metrics.csv",
]
CANDIDATES = [
    "gateway_metrics.jsonl",
    os.path.join("gateway", "gateway_metrics.jsonl"),
    os.path.join("logs", "gateway_metrics.jsonl"),
]


def load(path):
    rows, bad = [], 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                bad += 1
                continue
            if isinstance(r, dict) and "timestamp" in r:
                rows.append(r)
            else:
                bad += 1
    return rows, bad


def pct(vals, p):
    s = sorted(vals)
    k = max(0, -(-p * len(s) // 100) - 1)  # nearest rank, ceil
    return s[int(k)]


def line(label, ms):
    ms = [v for v in ms if v is not None]
    if not ms:
        print(f"  {label:<30} no data")
        return
    print(
        f"  {label:<30} n={len(ms):<4} p50={pct(ms, 50) / 1000:7.2f}s  "
        f"p95={pct(ms, 95) / 1000:7.2f}s  max={max(ms) / 1000:8.2f}s"
    )


def stamp(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def parse_since(s):
    try:
        return float(s)
    except ValueError:
        d = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return d.timestamp()


def by_action(rows):
    g = defaultdict(list)
    for r in rows:
        g[r.get("swap_action", "?")].append(r)
    return g


def load_gpu(path, since):
    rows, bad = [], 0
    with open(path, encoding="utf-8", newline="") as f:
        for rec in csv.DictReader(f, skipinitialspace=True):
            try:
                ts = datetime.strptime(
                    rec["timestamp"].strip(), "%Y/%m/%d %H:%M:%S.%f"
                ).timestamp()  # naive stamp = this machine's local time
                row = (
                    ts,
                    float(rec["gpu_util_pct"]),
                    float(rec["vram_used_mib"]),
                    float(rec["vram_total_mib"]),
                    float(rec["temp_c"]),
                    float(rec["power_w"]),
                )
            except (KeyError, ValueError, TypeError):
                bad += 1
                continue
            if since is None or ts >= since:
                rows.append(row)
    return sorted(rows), bad


def gpu_section(path, since):
    print("\n== GPU (gpu_metrics.csv, sampled every 30 s) ==")
    path = path or next((p for p in GPU_CANDIDATES if os.path.exists(p)), None)
    if not path or not os.path.exists(path):
        print("  gpu_metrics.csv not found; pass it with --gpu")
        return
    g, bad = load_gpu(path, since)
    if len(g) < 2:
        print("  not enough samples in the window")
        return
    n = len(g)
    util = [r[1] for r in g]
    vram = [r[2] for r in g]
    temp = [r[4] for r in g]
    power = [r[5] for r in g]
    total = g[-1][3]
    gaps = [b[0] - a[0] for a, b in zip(g, g[1:]) if b[0] - a[0] > SAMPLE_GAP_S]
    longest = cur = 0
    prev = None
    for ts, u, *_ in g:
        if prev is not None and ts - prev > SAMPLE_GAP_S:
            cur = 0
        cur = cur + 1 if u >= BUSY_PCT else 0
        longest = max(longest, cur)
        prev = ts
    share = lambda k: 100 * k / n
    print(f"  samples: {n}, {stamp(g[0][0])} -> {stamp(g[-1][0])} ({bad} unreadable rows skipped)")
    print(f"  logger gaps (> {SAMPLE_GAP_S} s): {len(gaps)}, total {sum(gaps) / 3600:.1f} h")
    print(f"  utilisation: p50 {pct(util, 50):.0f}%  p95 {pct(util, 95):.0f}%  max {max(util):.0f}%")
    print(
        f"  busy (>= {BUSY_PCT}%): {share(sum(u >= BUSY_PCT for u in util)):.1f}%   "
        f"idle (< {IDLE_PCT}%): {share(sum(u < IDLE_PCT for u in util)):.1f}%   "
        f"high (>= {HIGH_PCT}%): {share(sum(u >= HIGH_PCT for u in util)):.1f}%"
    )
    print(f"  longest continuous busy stretch: about {longest * 30} s")
    print(
        f"  VRAM used: min {min(vram):.0f}  peak {max(vram):.0f} of {total:.0f} MiB "
        f"(headroom at peak {total - max(vram):.0f} MiB)"
    )
    print(f"  temperature: median {pct(temp, 50):.0f} C  max {max(temp):.0f} C")
    print(f"  power: mean {sum(power) / n:.0f} W  max {max(power):.0f} W")
    print("  note: instant samples every 30 s can miss short bursts, so busy share is a floor")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default=None)
    ap.add_argument("--since", default=None)
    ap.add_argument("--gpu", default=None, help="path to gpu_metrics.csv")
    args = ap.parse_args()

    path = args.path or next((p for p in CANDIDATES if os.path.exists(p)), None)
    if not path or not os.path.exists(path):
        sys.exit("gateway_metrics.jsonl not found; pass its path as an argument")

    rows, bad = load(path)
    if args.since:
        t0 = parse_since(args.since)
        rows = [r for r in rows if r["timestamp"] >= t0]
    if not rows:
        sys.exit("no rows in the selected window")

    cancelled_all = [r for r in rows if r.get("event") == "client_cancelled"]
    cancelled = [r for r in cancelled_all if r["timestamp"] >= JUNK_BEFORE]
    junk = len(cancelled_all) - len(cancelled)
    replies = [r for r in rows if r.get("event") == "gateway_reply"]
    plain = [r for r in rows if "event" not in r]
    titles = [r for r in plain if r.get("stream") is False]
    answers = [r for r in plain if r.get("stream") is True]
    images = [r for r in answers if r.get("has_image")]
    docs = [r for r in answers if r.get("doc_count") and not r.get("has_image")]
    chat = [r for r in answers if not r.get("has_image") and not r.get("doc_count")]

    print(f"File: {path}")
    print(f"Window: {stamp(rows[0]['timestamp'])}  ->  {stamp(rows[-1]['timestamp'])}")
    print(f"Rows: {len(rows)} read, {bad} unreadable lines skipped")
    print(
        f"Split: {len(chat)} plain chat, {len(docs)} document, {len(images)} image, "
        f"{len(titles)} title (stream:false, excluded), {len(replies)} gateway replies, "
        f"{len(cancelled)} cancelled (+{junk} pre-fix junk excluded)"
    )

    print("\n== Plain chat (completed text answers) ==")
    with_ttft = [r for r in chat if r.get("ttft_ms") is not None]
    print(f"  rows with ttft: {len(with_ttft)} of {len(chat)} (older rows predate ttft logging)")
    for action, rs in sorted(by_action(with_ttft).items()):
        line(f"ttft  [{action}]", [r["ttft_ms"] for r in rs])
    for action, rs in sorted(by_action(chat).items()):
        line(f"total [{action}]", [r.get("gateway_total_ms") for r in rs])
    warm = [r for r in with_ttft if r.get("swap_action") == "already_loaded"]
    if warm:
        queued = [r for r in warm if r["ttft_ms"] > QUEUED_TTFT_MS]
        print(
            f"  likely queued (already_loaded, ttft > {QUEUED_TTFT_MS} ms): "
            f"{len(queued)} of {len(warm)} ({100 * len(queued) / len(warm):.0f}%)"
        )
    tps = []
    for r in with_ttft:
        o, t, g = r.get("output_tokens"), r["ttft_ms"], r.get("gateway_total_ms")
        if o and o >= 100 and g and g - t > 500:
            tps.append(o / ((g - t) / 1000))
    if tps:
        print(
            f"  decode speed (answers >= 100 tokens): median {pct(tps, 50):.0f} tok/s, "
            f"min {min(tps):.0f}, max {max(tps):.0f}  (n={len(tps)})"
        )

    print("\n== Document turns ==")
    if docs:
        fresh = [r for r in docs if not r.get("doc_cache_hits")]
        hits = len(docs) - len(fresh)
        print(f"  {len(docs)} turns, {hits} served fully from cache")
        line("convert (uncached)", [r.get("doc_convert_ms") for r in fresh])
        line("gateway total", [r.get("gateway_total_ms") for r in docs])
        over = [r for r in fresh if (r.get("doc_convert_ms") or 0) > CONVERT_LIMIT_MS]
        print(f"  conversions over {CONVERT_LIMIT_MS // 1000} s: {len(over)}")
        slow = sorted(fresh, key=lambda r: r.get("doc_convert_ms") or 0, reverse=True)[:3]
        for r in slow:
            print(
                f"  slowest: convert {r['doc_convert_ms'] / 1000:.1f} s, "
                f"{r.get('doc_chars')} doc chars, {r.get('prompt_tokens')} prompt tokens"
            )
        print("  (page count is not logged; per-page speed needs the Docling log)")
    else:
        print("  none")

    print("\n== Image turns ==")
    if images:
        for action, rs in sorted(by_action(images).items()):
            line(f"total [{action}]", [r.get("gateway_total_ms") for r in rs])
    else:
        print("  none")

    print("\n== Cancelled (Stop / dropped connection) ==")
    if cancelled:
        line("time until cancel", [r.get("gateway_total_ms") for r in cancelled])
        line("ttft at cancel", [r.get("ttft_ms") for r in cancelled])
    else:
        print("  none")

    print("\n== Gateway replies (errors shown to users) ==")
    if replies:
        for reason, n in Counter(r.get("reason", "?") for r in replies).most_common():
            print(f"  {reason}: {n}")
    else:
        print("  none")

    print("\n== Title requests (info only) ==")
    swapped = [r for r in titles if r.get("swap_action") != "already_loaded"]
    line("total", [r.get("gateway_total_ms") for r in titles])
    print(f"  paid a model load or swap: {len(swapped)} of {len(titles)}")

    gpu_section(args.gpu, parse_since(args.since) if args.since else None)


if __name__ == "__main__":
    main()