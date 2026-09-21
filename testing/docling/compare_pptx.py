"""
Compare two ways of reading the same PowerPoint file.

  Docling    : the file is sent straight to our Docling service (/convert).
  LibreChat  : the text LibreChat's own upload handling put in the chat. It is
               read from the gateway's request capture (GATEWAY_DUMP_DIR), i.e.
               exactly what the model was given.

Then, for each one:
  1. FACT SCORE   which known facts (made by make_test_pptx.py) appear at all
  2. ORDER        whether slides come out in order
  3. Q&A SCORE    the same questions asked of the model with each text

Run (defaults shown):
    python compare_pptx.py --pptx test.pptx --facts test_pptx_facts.json ^
        --dump-dir gateway\\gateway_dump --docling http://127.0.0.1:8001 ^
        --gateway http://127.0.0.1:8000

Add --no-qa to skip the model questions. Writes:
    pptx_out_docling.md  pptx_out_librechat.txt  pptx_comparison.md
"""

import argparse
import glob
import json
import os
import re
import sys
import time

import requests

ap = argparse.ArgumentParser()
ap.add_argument("--pptx", default="test.pptx")
ap.add_argument("--facts", default="test_pptx_facts.json")
ap.add_argument("--dump-dir", default=os.path.join("gateway", "gateway_dump"))
ap.add_argument("--docling", default="http://127.0.0.1:8001")
ap.add_argument("--gateway", default="http://127.0.0.1:8000")
ap.add_argument("--no-qa", action="store_true")
args = ap.parse_args()

spec = json.load(open(args.facts, encoding="utf-8"))
facts, qa = spec["facts"], spec["qa"]
MARKERS = [f["re"] for f in facts if f["id"] in ("title", "subtitle_code")]


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", t)


# ------------------------------------------------------------------ Docling
docling_text, docling_note = None, ""
try:
    t0 = time.monotonic()
    r = requests.post(
        f"{args.docling}/convert",
        data=open(args.pptx, "rb").read(),
        headers={"X-Filename": os.path.basename(args.pptx), "Content-Type": "application/octet-stream"},
        timeout=300,
    )
    if r.status_code == 200:
        docling_text = r.json()["markdown"]
        docling_note = f"{(time.monotonic() - t0):.1f}s"
    else:
        docling_note = f"HTTP {r.status_code}: {r.text[:120]}"
except requests.RequestException as e:
    docling_note = f"could not reach Docling ({type(e).__name__})"

# --------------------------------------------------------- LibreChat capture
libre_text, libre_note = None, ""
files = sorted(glob.glob(os.path.join(args.dump_dir, "*.json")), key=os.path.getmtime, reverse=True)
if not files:
    libre_note = f"no captured requests in {args.dump_dir}"
for path in files:
    d = json.load(open(path, encoding="utf-8"))
    raw_has_pptx_file = any(
        isinstance(m.get("content"), list)
        and any(p.get("type") == "file" and str(p.get("file", {}).get("filename", "")).lower().endswith((".pptx", ".ppt")) for p in m["content"])
        for m in d.get("raw", [])
    )
    for m in d.get("final") or []:
        content = m.get("content", "")
        if m.get("role") == "user" and isinstance(content, str) and any(re.search(x, content, re.I) for x in MARKERS):
            if raw_has_pptx_file:
                libre_note = "LibreChat forwarded the .pptx as a file; our gateway converted it with Docling, so there is no separate LibreChat text"
            else:
                libre_text, libre_note = content, f"from {os.path.basename(path)}"
            break
    if libre_text or raw_has_pptx_file:
        break
if libre_text is None and not libre_note:
    libre_note = "no captured request contained the deck's text (LibreChat may have refused or ignored the file)"

if docling_text:
    open("pptx_out_docling.md", "w", encoding="utf-8").write(docling_text)
if libre_text:
    open("pptx_out_librechat.txt", "w", encoding="utf-8").write(libre_text)


# ------------------------------------------------------------------ scoring
def score_facts(text):
    if text is None:
        return None
    t = norm(text)
    return {f["id"]: bool(re.search(f["re"], t, re.I | re.S)) for f in facts}


def order_ok(text):
    """Do slides appear in order? Compare the earliest position of each slide's facts."""
    if text is None:
        return None
    t = norm(text)
    first = {}
    for f in facts:
        m = re.search(f["re"], t, re.I | re.S)
        if m:
            first[f["slide"]] = min(first.get(f["slide"], 10**9), m.start())
    slides = sorted(first)
    bad = [(a, b) for a, b in zip(slides, slides[1:]) if first[a] > first[b]]
    return ("yes" if not bad else "no: slides " + ", ".join(f"{a}/{b}" for a, b in bad)), len(slides)


sources = {"Docling": docling_text, "LibreChat": libre_text}
fact_scores = {k: score_facts(v) for k, v in sources.items()}
orders = {k: order_ok(v) for k, v in sources.items()}


def ask(text, question):
    content = f"{text}\n\nQuestion: {question}\nAnswer in one short sentence."
    try:
        r = requests.post(
            f"{args.gateway}/v1/chat/completions",
            json={"stream": False, "messages": [{"role": "user", "content": content}]},
            timeout=300,
        )
    except requests.RequestException as e:
        return None, f"ERROR ({type(e).__name__})"
    if r.status_code != 200:
        try:
            msg = r.json()["error"]["message"]
        except Exception:
            msg = r.text[:100]
        return None, f"ERROR: {msg}"
    return r.json()["choices"][0]["message"]["content"].strip(), None


qa_scores = {k: None for k in sources}
qa_answers = {k: [] for k in sources}
if not args.no_qa:
    for k, text in sources.items():
        if text is None:
            continue
        got = 0
        for item in qa:
            answer, err = ask(text, item["q"])
            ok = bool(answer) and any(a.lower() in answer.lower() for a in item["any"])
            got += ok
            qa_answers[k].append((item["q"], answer or err, ok))
        qa_scores[k] = got

# ------------------------------------------------------------------- report
lines = []
w = lines.append
w(f"# PPTX comparison: {os.path.basename(args.pptx)}\n")
w(f"- Docling   : {docling_note or 'ok'}; {len(docling_text) if docling_text else 0} characters")
w(f"- LibreChat : {libre_note or 'ok'}; {len(libre_text) if libre_text else 0} characters\n")
w("## 1. Facts found (each fact is something a good parser should keep)\n")
w("| Slide | What | Docling | LibreChat |")
w("|---|---|---|---|")
for f in facts:
    def cell(k):
        s = fact_scores[k]
        return "-" if s is None else ("yes" if s[f["id"]] else "MISSING")
    w(f"| {f['slide']} | {f['kind']} ({f['id']}) | {cell('Docling')} | {cell('LibreChat')} |")
tot = len(facts)
def total(k):
    s = fact_scores[k]
    return "no text" if s is None else f"{sum(s.values())}/{tot}"
w(f"| | **Total** | **{total('Docling')}** | **{total('LibreChat')}** |\n")
w("## 2. Slide order\n")
for k in sources:
    o = orders[k]
    w(f"- {k}: " + ("no text" if o is None else f"{o[0]} ({o[1]} of {spec['slides']} slides identifiable)"))
if not args.no_qa:
    w("\n## 3. Questions answered by the model using each text\n")
    w("| Question | Docling | LibreChat |")
    w("|---|---|---|")
    for i, item in enumerate(qa):
        def qcell(k):
            if not qa_answers[k]:
                return "-"
            q, a, ok = qa_answers[k][i]
            return ("right" if ok else "WRONG") + f": {str(a)[:70]}"
        w(f"| {item['q']} | {qcell('Docling')} | {qcell('LibreChat')} |")
    def qtot(k):
        return "no text" if qa_scores[k] is None else f"{qa_scores[k]}/{len(qa)}"
    w(f"| **Total** | **{qtot('Docling')}** | **{qtot('LibreChat')}** |")
report = "\n".join(lines)
open("pptx_comparison.md", "w", encoding="utf-8").write(report)
print(report)
print("\nSaved: pptx_comparison.md" + ("  pptx_out_docling.md" if docling_text else "") + ("  pptx_out_librechat.txt" if libre_text else ""))
