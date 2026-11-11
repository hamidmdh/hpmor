#!/usr/bin/env python3
"""Copy only the publishable static files into _site/ for GitHub Pages."""
from __future__ import annotations

import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    for name in ("index.html", "about.html", ".nojekyll"):
        shutil.copy2(ROOT / name, OUT / name)
    for page in sorted(ROOT.glob("chapter*.html")):
        shutil.copy2(page, OUT / page.name)
    shutil.copytree(ROOT / "assets", OUT / "assets")
    count = len(list(OUT.glob("chapter*.html")))
    print(f"packaged {count} chapter pages into {OUT}")


if __name__ == "__main__":
    main()
