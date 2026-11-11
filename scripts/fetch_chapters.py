#!/usr/bin/env python3
"""Fetch the English text of HPMOR from the annotated mirror hpmor.info.

Source: https://hpmor.info/chapter/<n>/
Output: data/ch<nnn>_source.json

Each output entry:
  {"n": <local paragraph number>, "html": "<inline-safe html>",
   "text": "<plain text>", "break_before": <bool>}
"""
from __future__ import annotations

import argparse
import html as htmllib
import json
import pathlib
import re
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
BASE = "https://hpmor.info/chapter/{n}/"
UA = "Mozilla/5.0 (X11; Linux x86_64) hpmor-translation-builder/1.0"

PARA_RE = re.compile(
    r'<a id="(?P<n>\d+)"></a><span class="para-number">.*?</span>\s*'
    r'(?P<body>.*?)</p>',
    re.S,
)
TITLE_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
TAG_RE = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)([^>]*)>")
ALLOWED = {"em", "strong", "br"}


def fetch(n: int, cache: bool = True) -> str:
    RAW.mkdir(parents=True, exist_ok=True)
    raw_path = RAW / f"ch{n}.html"
    if cache and raw_path.exists() and raw_path.stat().st_size > 1000:
        return raw_path.read_text(encoding="utf-8")
    req = urllib.request.Request(BASE.format(n=n), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        text = resp.read().decode("utf-8")
    raw_path.write_text(text, encoding="utf-8")
    return text


def clean_inline(fragment: str) -> str:
    """Keep only em/strong/br, drop every other tag but keep its text."""
    out = []
    pos = 0
    for m in TAG_RE.finditer(fragment):
        out.append(fragment[pos : m.start()])
        closing, name, _attrs = m.group(1), m.group(2).lower(), m.group(3)
        if name in ALLOWED:
            out.append(f"<{closing}{name}>" if name != "br" else "<br>")
        pos = m.end()
    out.append(fragment[pos:])
    text = "".join(out)
    # Normalise whitespace inside text nodes while keeping tags intact.
    text = re.sub(r"[ \t\r\n]+", " ", text)
    text = re.sub(r"<br>\s*", "<br>", text)
    text = re.sub(r"\s*</(em|strong)>", r"</\1>", text)
    text = re.sub(r"<(em|strong)>\s+", r"<\1>", text)
    return text.strip()


def plain(fragment: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", fragment)
    text = re.sub(r"<[^>]+>", "", text)
    text = htmllib.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def parse(n: int, page: str) -> dict:
    title_m = TITLE_RE.search(page)
    if not title_m:
        raise ValueError(f"chapter {n}: no <h1> title")
    title = plain(clean_inline(title_m.group(1)))
    title = re.sub(r"^Chapter\s+\d+\s*:\s*", "", title, flags=re.I).strip()

    paragraphs = []
    # Splitting on paragraph wrappers lets us mark <hr> scene breaks.
    chunks = re.split(r'(?=<div class="paragraph)', page)
    pending_break = False
    for chunk in chunks:
        if '<div class="paragraph' not in chunk:
            continue
        m = PARA_RE.search(chunk)
        if not m:
            raise ValueError(f"chapter {n}: unparsable paragraph chunk")
        body = clean_inline(m.group("body"))
        paragraphs.append(
            {
                "n": int(m.group("n")),
                "local": len(paragraphs) + 1,
                "html": body,
                "text": plain(body),
                "break_before": pending_break,
            }
        )
        pending_break = False
        # A short scene break follows as <div><hr></div> before the next paragraph.
        tail = chunk[m.end() :]
        if re.search(r"<hr\s*/?>", tail):
            pending_break = True

    if not paragraphs:
        raise ValueError(f"chapter {n}: no paragraphs")
    nums = [p["n"] for p in paragraphs]
    if nums != list(range(nums[0], nums[0] + len(nums))):
        raise ValueError(f"chapter {n}: non-contiguous paragraph numbers {nums[:5]}...")

    return {"chapter": n, "title": title, "source": BASE.format(n=n), "paragraphs": paragraphs}


def save(ch: dict) -> pathlib.Path:
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / f"ch{ch['chapter']:03d}_source.json"
    path.write_text(json.dumps(ch, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("chapters", nargs="*", help="chapter numbers (default: 1..122)")
    ap.add_argument("--delay", type=float, default=0.4)
    ap.add_argument("--offline", action="store_true", help="only use cached raw pages")
    args = ap.parse_args()
    numbers = [int(x) for x in args.chapters] or list(range(1, 123))
    for i, n in enumerate(numbers):
        page = fetch(n, cache=not args.offline)
        ch = parse(n, page)
        path = save(ch)
        print(f"{path.name}: {ch['title']!r}, {len(ch['paragraphs'])} paragraphs")
        if i + 1 < len(numbers):
            time.sleep(args.delay)
    return 0


if __name__ == "__main__":
    sys.exit(main())
