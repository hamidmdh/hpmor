#!/usr/bin/env python3
"""Machine-translate all remaining HPMOR chapters into Persian.

Usage:
  python3 scripts/machine_translate.py 3          # one chapter (test)
  python3 scripts/machine_translate.py 3-122      # range
  python3 scripts/machine_translate.py --all      # 3..122, skip existing
  --force                                         # overwrite existing
  --workers 4 --batch-chars 3500

The output files have "translation": "machine" so the site can label them.
Chapters 1 and 2 are hand translations and are skipped by default.

Translation uses Google's public gtx endpoint; results are cached under
data/mt_cache/ so an interrupted run can resume without re-requesting.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CACHE = DATA / "mt_cache"
TOTAL = 122
ENDPOINT = "https://translate.googleapis.com/translate_a/single"
CLIENTS5 = "https://clients5.google.com/translate_a/t"
DELIM = "\n@@@\n"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122 Safari/537.36"
# The container proxy can disappear while a run is in progress. Talk to
# Google directly, and fall back between two public endpoints.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

STOPWORDS = set(
    """a an the and or but if then than that this these those of to in on at
    for with from by as is are was were be been being it its he she they them
    his her their you your i we our not no so do does did have has had will
    would can could should may might must about into over after before while
    during without within through up down out off again further once here there
    when where why how all any both each few more most other some such only own
    same too very just also now""".split()
)

# Names and setting terms that Google Translate mangles. Each entry is replaced
# by an opaque token before translation and restored afterwards. This keeps
# "McGonagall" from becoming "مک گونگال" and "barman" from becoming "باردار"
# (pregnant).
GLOSSARY = {
    "Harry Potter": "هری پاتر",
    "Harry": "هری",
    "Potter": "پاتر",
    "Hermione Granger": "هرماینی گرنجر",
    "Hermione": "هرماینی",
    "Ron Weasley": "ران ویزلی",
    "Ron": "ران",
    "Draco Malfoy": "دراکو مالفوی",
    "Draco": "دراکو",
    "Dumbledore": "دامبلدور",
    "McGonagall": "مک‌گوناگل",
    "Snape": "اسنیپ",
    "Quirrell": "کوئیرل",
    "Hagrid": "هاگرید",
    "Dumbledore's": "دامبلدور",
    "Voldemort": "ولدمورت",
    "Dumbledore": "دامبلدور",
    "Hogwarts": "هاگوارتز",
    "Gryffindor": "گریفیندور",
    "Slytherin": "اسلیترین",
    "Ravenclaw": "ریونکلاو",
    "Hufflepuff": "هافلپاف",
    "Diagon Alley": "کوچهٔ دیاگون",
    "Leaky Cauldron": "دیگ نشتی",
    "Madam Pomfrey": "مادام پامفری",
    "Madam Malkin": "مادام مالکین",
    "Professor Flitwick": "پروفسور فلیتویک",
    "Flitwick": "فلیتویک",
    "Professor Sprout": "پروفسور اسپروت",
    "Professor Quirrell": "پروفسور کوئیرل",
    "Azkaban": "آزکابان",
    "Muggle": "ماگل",
    "Muggles": "ماگل‌ها",
    "barman": "ساقی",
    "barmaid": "ساقی",
    "Tom": "تام",
    "Petunia": "پتونیا",
    "Dudley": "دادلی",
    "Vernon": "ورنون",
    "Lily": "لیلی",
    "James": "جیمز",
    "Sirius": "سیریوس",
    "Lupin": "لوپین",
    "Neville": "نویل",
    "Luna": "لونا",
    "Bellatrix": "بلاتریکس",
    "Dementor": "دیوانه‌ساز",
    "Dementors": "دیوانه‌سازها",
    "Azkaban": "آزکابان",
}

_TOKEN_RE = re.compile(r"ZQX(\d+)QZ")
_cache_lock = threading.Lock()


def shield(text: str) -> tuple[str, dict[str, str]]:
    """Replace glossary terms with opaque tokens, longest match first."""
    mapping: dict[str, str] = {}
    for index, term in enumerate(sorted(GLOSSARY, key=len, reverse=True)):
        pattern = re.compile(r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])")
        token = f"ZQX{index}QZ"
        if pattern.search(text):
            text = pattern.sub(token, text)
            mapping[token] = GLOSSARY[term]
    return text, mapping


def unshield(text: str, mapping: dict[str, str]) -> str:
    for token, term in mapping.items():
        text = text.replace(token, term)
    # Any token left over (Google occasionally re-cases it) is replaced by its
    # glossary entry if we can still recognise the index.
    def restore(match: re.Match[str]) -> str:
        return mapping.get(match.group(0), match.group(0))

    return _TOKEN_RE.sub(restore, text)


def load_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def summarize(texts: list[str], max_sentences: int) -> str:
    """Small extractive summary: score sentences by content-word frequency."""
    text = " ".join(texts)
    sentences = split_sentences(text)
    if not sentences:
        return text[:300]
    if len(sentences) <= max_sentences:
        return " ".join(sentences)
    words = re.findall(r"[A-Za-z][A-Za-z'-]+", text.lower())
    freq = Counter(w for w in words if len(w) > 2 and w not in STOPWORDS)
    scored = []
    for idx, sent in enumerate(sentences):
        sw = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]+", sent.lower()) if w not in STOPWORDS]
        if not sw:
            continue
        score = sum(freq[w] for w in sw) / (len(sw) + 4)
        if len(sent) < 25:
            score *= 0.5
        scored.append((score, idx, sent))
    # Always keep the opening sentence so the summary starts in context, then
    # add the highest-scoring sentences up to the limit.
    chosen_idx = [0]
    for _, idx, _ in sorted(scored, reverse=True):
        if len(chosen_idx) >= max_sentences:
            break
        if idx not in chosen_idx:
            chosen_idx.append(idx)
    chosen_idx.sort()
    out = " ".join(sentences[i] for i in chosen_idx)
    if len(out) > 420:
        out = out[:420].rsplit(" ", 1)[0] + "…"
    return out


def cache_path(text: str) -> pathlib.Path:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return CACHE / f"{digest}.txt"


def _request_json(url: str, data: bytes | None = None) -> list:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    with _OPENER.open(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _translate_gtx(text: str) -> str:
    data = urllib.parse.urlencode(
        {"client": "gtx", "sl": "en", "tl": "fa", "dt": "t", "q": text}
    ).encode()
    payload = _request_json(ENDPOINT, data)
    return "".join(seg[0] for seg in (payload[0] or []) if seg and seg[0])


def _translate_clients5(text: str) -> str:
    url = CLIENTS5 + "?" + urllib.parse.urlencode(
        {"client": "dict-chrome-ex", "sl": "en", "tl": "fa", "q": text}
    )
    payload = _request_json(url)
    if isinstance(payload, list) and payload and isinstance(payload[0], str):
        return "".join(payload)
    if isinstance(payload, list) and payload and isinstance(payload[0], list):
        return "".join(seg[0] for seg in payload[0] if seg and seg[0])
    raise ValueError(f"unexpected translation response: {str(payload)[:200]}")


def gtranslate(text: str) -> str:
    """Translate one string, with disk cache, endpoint fallback, and retries."""
    path = cache_path(text)
    if path.exists():
        return path.read_text(encoding="utf-8")
    last_error = None
    for attempt in range(6):
        for translate in (_translate_clients5, _translate_gtx):
            try:
                translated = translate(text)
                if not translated.strip():
                    raise ValueError("empty translation")
                CACHE.mkdir(parents=True, exist_ok=True)
                with _cache_lock:
                    path.write_text(translated, encoding="utf-8")
                return translated
            except Exception as exc:  # network, rate limit, malformed response
                last_error = exc
        wait = min(60, (2 ** attempt) + random.random() * 2)
        print(f"  retry {attempt + 1}/6 after {wait:.0f}s: {last_error}", flush=True)
        time.sleep(wait)
    raise RuntimeError(f"translation failed: {last_error}")


def make_batches(items: list[tuple[str, str]], max_chars: int) -> list[list[tuple[str, str]]]:
    batches: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    chars = 0
    for key, text in items:
        need = len(text) + len(DELIM)
        if current and chars + need > max_chars:
            batches.append(current)
            current, chars = [], 0
        current.append((key, text))
        chars += need
    if current:
        batches.append(current)
    return batches


def translate_batch(batch: list[tuple[str, str]]) -> dict[str, str]:
    shielded = []
    mappings: dict[str, dict[str, str]] = {}
    for key, text in batch:
        safe_text, mapping = shield(text)
        shielded.append((key, safe_text))
        mappings[key] = mapping
    joined = DELIM.join(text for _, text in shielded)
    translated = gtranslate(joined)
    parts = re.split(r"\s*@@@\s*", translated)
    if len(parts) != len(batch):
        print(
            f"  delimiter mismatch ({len(parts)} != {len(batch)}); translating individually",
            flush=True,
        )
        out = {}
        for key, safe_text in shielded:
            piece = unshield(gtranslate(safe_text), mappings[key])
            out[key] = piece.strip()
        return out
    return {
        key: unshield(part.strip(), mappings[key])
        for (key, _), part in zip(batch, parts)
    }


def sections_for(src: dict, size: int = 4) -> list[list[int]]:
    groups: list[list[int]] = []
    current: list[int] = []
    for para in src["paragraphs"]:
        if current and (len(current) >= size or para["break_before"]):
            groups.append(current)
            current = []
        current.append(para["n"])
    if current:
        groups.append(current)
    return groups


def translate_chapter(n: int, workers: int, batch_chars: int, force: bool) -> bool:
    out_path = DATA / f"ch{n:03d}.json"
    if out_path.exists() and not force:
        existing = load_json(out_path)
        if existing.get("translation") == "machine" or n <= 2:
            print(f"ch{n:03d}: already present, skipping", flush=True)
            return False
    src = load_json(DATA / f"ch{n:03d}_source.json")
    titles = load_json(DATA / "titles_fa.json")
    by_n = {p["n"]: p for p in src["paragraphs"]}
    groups = sections_for(src)

    sections = []
    items: list[tuple[str, str]] = []
    for sid, paras in enumerate(groups, start=1):
        texts = [by_n[p]["text"] for p in paras]
        summary_en = summarize(texts, 2 if len(texts) >= 4 else 1)
        sections.append(
            {
                "id": sid,
                "paras": paras,
                "summary_en": summary_en,
                "translation_fa": [],
                "summary_fa": "",
            }
        )
        for p in paras:
            items.append((f"p{p}", by_n[p]["text"]))
        items.append((f"s{sid}", summary_en))

    # Deduplicate identical texts while preserving keys.
    batches = make_batches(items, batch_chars)
    print(
        f"ch{n:03d}: {len(src['paragraphs'])} paragraphs, {len(groups)} sections, "
        f"{len(items)} strings, {len(batches)} batches",
        flush=True,
    )
    results: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(translate_batch, b): b for b in batches}
        done = 0
        for fut in as_completed(futures):
            results.update(fut.result())
            done += 1
            print(f"ch{n:03d}: batch {done}/{len(batches)}", flush=True)

    for sec in sections:
        sec["translation_fa"] = [results[f"p{p}"] for p in sec["paras"]]
        sec["summary_fa"] = results[f"s{sec['id']}"]

    data = {
        "chapter": n,
        "title": src["title"],
        "title_fa": titles[str(n)],
        "translation": "machine",
        "sections": sections,
    }
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"ch{n:03d}: wrote {out_path.name}", flush=True)
    return True


def parse_chapters(value: str) -> list[int]:
    if "-" in value:
        a, b = value.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(value)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("chapters", nargs="?")
    ap.add_argument("--all", action="store_true", help="translate chapters 3-122")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--batch-chars", type=int, default=3500)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if args.all:
        numbers = list(range(3, TOTAL + 1))
    elif args.chapters:
        numbers = parse_chapters(args.chapters)
    else:
        ap.error("give a chapter number, a range like 3-20, or --all")
    CACHE.mkdir(parents=True, exist_ok=True)
    started = time.time()
    changed = 0
    for n in numbers:
        if translate_chapter(n, args.workers, args.batch_chars, args.force):
            changed += 1
    print(
        f"done: {changed} chapters written in {time.time() - started:.0f}s",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
