#!/usr/bin/env python3
"""Create an empty translation skeleton for one chapter.

Usage:
  python3 scripts/scaffold_chapter.py 2
  python3 scripts/scaffold_chapter.py 2 --size 4

The generated data/chNNN.json groups paragraphs into short sections and
leaves the translations/summaries empty, ready to be filled in.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("chapter", type=int)
    ap.add_argument("--size", type=int, default=4, help="target paragraphs per section")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    n = args.chapter
    src_path = DATA / f"ch{n:03d}_source.json"
    if not src_path.exists():
        print(f"missing {src_path}; run scripts/fetch_chapters.py {n} first", file=sys.stderr)
        return 1
    out_path = DATA / f"ch{n:03d}.json"
    if out_path.exists() and not args.force:
        print(f"{out_path} already exists; use --force to overwrite", file=sys.stderr)
        return 1

    src = json.loads(src_path.read_text(encoding="utf-8"))
    titles = json.loads((DATA / "titles_fa.json").read_text(encoding="utf-8"))
    sections = []
    current: list[int] = []
    next_id = 1

    def flush() -> None:
        nonlocal current, next_id
        if not current:
            return
        sections.append(
            {
                "id": next_id,
                "paras": current,
                "summary_en": "",
                "translation_fa": ["" for _ in current],
                "summary_fa": "",
            }
        )
        next_id += 1
        current = []

    for para in src["paragraphs"]:
        if current and (len(current) >= args.size or para["break_before"]):
            flush()
        current.append(para["n"])
    flush()

    data = {
        "chapter": n,
        "title": src["title"],
        "title_fa": titles[str(n)],
        "sections": sections,
    }
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path} with {len(sections)} sections; fill translations and summaries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
