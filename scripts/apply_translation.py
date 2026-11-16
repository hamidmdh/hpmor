#!/usr/bin/env python3
"""Apply a paragraph translation map to one chapter.

Usage:
  python3 scripts/apply_translation.py 14 /tmp/ch014_fa.json

The map file must be a JSON object whose keys are paragraph numbers (as
strings) and whose values are the Persian translations. Every paragraph of the
chapter must be present exactly once. The chapter file keeps its existing
section layout and loses the ``translation`` marker and any leftover summary
fields, so the chapter becomes a hand translation.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    n = int(sys.argv[1])
    map_path = pathlib.Path(sys.argv[2])
    tr_path = DATA / f"ch{n:03d}.json"
    src_path = DATA / f"ch{n:03d}_source.json"

    tr = json.loads(tr_path.read_text(encoding="utf-8"))
    src = json.loads(src_path.read_text(encoding="utf-8"))
    raw = json.loads(map_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        fail("translation map must be a JSON object")

    expected = [p["n"] for p in src["paragraphs"]]
    mapped: dict[int, str] = {}
    for key, value in raw.items():
        try:
            pn = int(key)
        except (TypeError, ValueError):
            fail(f"non-numeric paragraph key: {key!r}")
        if pn in mapped:
            fail(f"duplicate paragraph key {pn}")
        if not isinstance(value, str) or not value.strip():
            fail(f"empty translation for paragraph {pn}")
        mapped[pn] = value.strip()

    missing = [p for p in expected if p not in mapped]
    extra = [p for p in mapped if p not in set(expected)]
    if missing:
        fail(f"missing paragraphs: {missing[:20]}{'…' if len(missing) > 20 else ''}")
    if extra:
        fail(f"unknown paragraphs: {extra[:20]}")

    for sec in tr.get("sections", []):
        sec.pop("summary_en", None)
        sec.pop("summary_fa", None)
        sec["translation_fa"] = [mapped[p] for p in sec["paras"]]
    tr.pop("translation", None)
    tr_path.write_text(
        json.dumps(tr, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"applied {len(expected)} translations to {tr_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
