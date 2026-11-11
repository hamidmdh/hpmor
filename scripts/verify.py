#!/usr/bin/env python3
"""Verify source data, translation coverage, and built pages.

Run from the repo root: python3 scripts/verify.py
Exit code 0 means everything is consistent.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TOTAL = 122
ALLOWED_TAGS = {"em", "strong", "br"}
TAG_RE = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)[^>]*>")


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def load(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    titles = load(DATA / "titles_fa.json")
    missing_titles = [n for n in range(1, TOTAL + 1) if not titles.get(str(n))]
    if missing_titles:
        fail(f"titles_fa.json missing: {missing_titles}")

    translated = []
    total_paragraphs = 0
    total_sections = 0
    for n in range(1, TOTAL + 1):
        src_path = DATA / f"ch{n:03d}_source.json"
        if not src_path.exists():
            fail(f"missing {src_path.name}")
        src = load(src_path)
        if src.get("chapter") != n:
            fail(f"{src_path.name}: chapter is {src.get('chapter')}, expected {n}")
        if not src.get("title"):
            fail(f"{src_path.name}: empty title")
        paras = src.get("paragraphs", [])
        if not paras:
            fail(f"{src_path.name}: no paragraphs")
        nums = [p.get("n") for p in paras]
        if nums != list(range(nums[0], nums[0] + len(nums))):
            fail(f"{src_path.name}: paragraph numbers are not contiguous")
        for p in paras:
            if not p.get("text", "").strip():
                fail(f"{src_path.name}: paragraph {p.get('n')} is empty")
            for closing, tag in TAG_RE.findall(p.get("html", "")):
                if tag.lower() not in ALLOWED_TAGS:
                    fail(f"{src_path.name}: unexpected <{tag}> in paragraph {p.get('n')}")
        total_paragraphs += len(paras)

        tr_path = DATA / f"ch{n:03d}.json"
        if not tr_path.exists():
            page = ROOT / f"chapter{n}.html"
            if not page.exists():
                fail(f"missing built page {page.name}")
            continue
        tr = load(tr_path)
        if tr.get("chapter") != n:
            fail(f"{tr_path.name}: chapter mismatch")
        if not tr.get("title_fa", "").strip():
            fail(f"{tr_path.name}: missing title_fa")
        sections = tr.get("sections", [])
        if not sections:
            fail(f"{tr_path.name}: no sections")
        covered = []
        for sec in sections:
            sid = sec.get("id")
            sec_paras = sec.get("paras", [])
            translations = sec.get("translation_fa", [])
            if len(sec_paras) != len(translations):
                fail(f"{tr_path.name} section {sid}: paragraph/translation count mismatch")
            if not str(sec.get("summary_en", "")).strip():
                fail(f"{tr_path.name} section {sid}: missing summary_en")
            if not str(sec.get("summary_fa", "")).strip():
                fail(f"{tr_path.name} section {sid}: missing summary_fa")
            for pn, text in zip(sec_paras, translations):
                if not str(text).strip():
                    fail(f"{tr_path.name} section {sid}: empty translation for paragraph {pn}")
            covered.extend(sec_paras)
        if covered != nums:
            fail(f"{tr_path.name}: sections do not cover every paragraph in order")
        page = ROOT / f"chapter{n}.html"
        if not page.exists():
            fail(f"missing built page {page.name}")
        html = page.read_text(encoding="utf-8")
        if 'dir="rtl"' not in html or "ترجمهٔ فارسی" not in html:
            fail(f"{page.name}: missing RTL translation column")
        translated.append(n)
        total_sections += len(sections)

    # Index sanity checks.
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    if index.count('class="chapter-card"') != TOTAL:
        fail(f"index.html should list {TOTAL} chapters")
    about = ROOT / "about.html"
    if not about.exists():
        fail("missing about.html")
    if not (ROOT / ".nojekyll").exists():
        fail("missing .nojekyll")

    print(f"OK: {TOTAL} source chapters, {total_paragraphs:,} English paragraphs")
    print(f"OK: {len(translated)}/{TOTAL} translated chapters, {total_sections} sections")
    if translated:
        print(f"Translated: {', '.join(map(str, translated))}")
    print(f"OK: index.html lists {TOTAL} chapters; about.html and .nojekyll present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
