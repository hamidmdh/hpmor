#!/usr/bin/env python3
"""Build the static HPMOR Persian parallel-reading site.

Inputs:
  data/chNNN_source.json   English paragraphs fetched from hpmor.info
  data/chNNN.json          optional Persian translation (sections)
  data/titles_fa.json      Persian chapter titles

Outputs:
  index.html, about.html, chapter1.html .. chapter122.html
"""
from __future__ import annotations

import html as htmllib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TOTAL = 122
REPO_URL = "https://github.com/hamidmdh/hpmor"
SITE_NAME = "هری پاتر و روش‌های عقلانیت"
SITE_TAGLINE = "ترجمهٔ فارسی موازی"

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa_num(value: int | str) -> str:
    return str(value).translate(FA_DIGITS)


def esc(text: str) -> str:
    return htmllib.escape(text, quote=False)


def load_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_path(n: int) -> pathlib.Path:
    return DATA / f"ch{n:03d}_source.json"


def translation_path(n: int) -> pathlib.Path:
    return DATA / f"ch{n:03d}.json"


def chapter_url(n: int) -> str:
    return f"chapter{n}.html"


def load_source(n: int) -> dict:
    return load_json(source_path(n))


def load_titles() -> dict[str, str]:
    titles = load_json(DATA / "titles_fa.json")
    missing = [str(n) for n in range(1, TOTAL + 1) if not titles.get(str(n))]
    if missing:
        raise SystemExit(f"titles_fa.json is missing chapters: {', '.join(missing)}")
    return titles


def validate_translation(src: dict, tr: dict) -> None:
    n = src["chapter"]
    if tr.get("chapter") != n:
        raise SystemExit(f"ch{n}: chapter number mismatch in translation file")
    source_ns = [p["n"] for p in src["paragraphs"]]
    covered: list[int] = []
    seen_ids: set[int] = set()
    for sec in tr.get("sections", []):
        sid = sec.get("id")
        if sid in seen_ids:
            raise SystemExit(f"ch{n}: duplicate section id {sid}")
        seen_ids.add(sid)
        paras = sec.get("paras", [])
        trans = sec.get("translation_fa", [])
        if len(paras) != len(trans):
            raise SystemExit(
                f"ch{n} section {sid}: {len(paras)} paragraphs but {len(trans)} translations"
            )
        for pn, text in zip(paras, trans):
            if not str(text).strip():
                raise SystemExit(f"ch{n} section {sid}: empty translation for paragraph {pn}")
        if not str(sec.get("summary_en", "")).strip():
            raise SystemExit(f"ch{n} section {sid}: missing summary_en")
        if not str(sec.get("summary_fa", "")).strip():
            raise SystemExit(f"ch{n} section {sid}: missing summary_fa")
        covered.extend(paras)
    if covered != source_ns:
        missing = sorted(set(source_ns) - set(covered))
        extra = sorted(set(covered) - set(source_ns))
        raise SystemExit(
            f"ch{n}: section coverage mismatch; missing={missing[:12]} extra={extra[:12]}"
        )


def fa_paragraph(text: str) -> str:
    """Render one translated paragraph, preserving line breaks and simple * lists."""
    text = str(text).replace("\r\n", "\n").strip()
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) > 1 and all(line.startswith("* ") for line in lines):
        items = "".join(f"<li>{esc(line[2:].strip())}</li>" for line in lines)
        return f"<ul>{items}</ul>"
    return f"<p>{'<br>'.join(esc(line) for line in lines)}</p>"


def en_paragraph(fragment: str) -> str:
    """Render one English source paragraph (already limited to em/strong/br)."""
    parts = re.split(r"<br\s*/?>", fragment)
    if len(parts) > 1 and all(p.strip().startswith("* ") for p in parts if p.strip()):
        items = "".join(f"<li>{p.strip()[2:].strip()}</li>" for p in parts if p.strip())
        return f"<ul>{items}</ul>"
    return f"<p>{fragment}</p>"


def plain_summary(text: str) -> str:
    return f"<p>{esc(str(text).strip())}</p>"


def brand_svg() -> str:
    return (
        '<svg viewBox="0 0 64 64" aria-hidden="true">'
        '<rect width="64" height="64" rx="14" fill="#0f6b62"/>'
        '<path d="M35 8 18 36h11l-3 20 20-31H34l1-17z" fill="#f7f3ea"/>'
        "</svg>"
    )


def header_html(active: str = "") -> str:
    def link(href: str, label: str, key: str) -> str:
        cur = ' aria-current="page"' if active == key else ""
        return f'<a href="{href}"{cur}>{label}</a>'

    return f"""<header class="site-header">
  <div class="wrap">
    <a class="brand" href="index.html">{brand_svg()}<span>{SITE_NAME}</span></a>
    <nav class="site-nav" aria-label="ناوبری اصلی">
      {link("index.html", "فهرست فصل‌ها", "index")}
      {link("about.html", "دربارهٔ پروژه", "about")}
      <a href="{REPO_URL}" rel="noopener">GitHub</a>
    </nav>
  </div>
</header>"""


def footer_html() -> str:
    return f"""<footer class="site-footer">
  <div class="wrap">
    <p>ترجمهٔ فارسی غیررسمی و غیرتجاری از <em>Harry Potter and the Methods of Rationality</em>.</p>
    <p>متن اصلی نوشتهٔ الیزر یودکوفسکی است و به‌صورت رایگان در <a href="https://hpmor.com/" rel="noopener">hpmor.com</a> منتشر شده است. هری پاتر © جی.کی. رولینگ · HPMOR © Eliezer Yudkowsky.</p>
    <p class="en">English source mirror: <a href="https://hpmor.info/" rel="noopener">hpmor.info</a> · Code and translations: <a href="{REPO_URL}" rel="noopener">github.com/hamidmdh/hpmor</a></p>
  </div>
</footer>"""


def page_shell(title: str, body: str, active: str = "", script: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="ترجمهٔ فارسی موازی هری پاتر و روش‌های عقلانیت: متن اصلی انگلیسی، خلاصهٔ انگلیسی، ترجمهٔ فارسی و خلاصهٔ فارسی.">
<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&amp;family=Vazirmatn:wght@400;500;700&amp;display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/styles.css">
</head>
<body>
{header_html(active)}
{body}
{footer_html()}
{script}
</body>
</html>
"""


def chapter_nav(n: int, titles: dict[str, str]) -> str:
    def item(target: int, direction: str) -> str:
        if target < 1 or target > TOTAL:
            return '<span class="spacer"></span>'
        label = "فصل قبل" if target < n else "فصل بعد"
        cls = "prev" if target < n else "next"
        return (
            f'<a class="{cls}" href="{chapter_url(target)}">'
            f'<span class="dir">{label} · فصل {fa_num(target)}</span>'
            f'<span class="t">{esc(titles[str(target)])}</span></a>'
        )

    return f'<nav class="chapter-nav" aria-label="فصل‌های مجاور">{item(n - 1, "prev")}{item(n + 1, "next")}</nav>'


def toolbar_html() -> str:
    return """<div class="toolbar" role="group" aria-label="انتخاب ستون‌ها">
  <span class="toolbar-label">نمایش:</span>
  <button class="mode-btn" type="button" data-mode="all" aria-pressed="true">همهٔ ستون‌ها</button>
  <button class="mode-btn" type="button" data-mode="fa" aria-pressed="false">فقط فارسی</button>
  <button class="mode-btn" type="button" data-mode="en" aria-pressed="false">فقط انگلیسی</button>
  <span class="toolbar-label" style="margin-inline-start:auto">کلیک روی شمارهٔ بخش برای پیوند مستقیم</span>
</div>"""


MODE_SCRIPT = """<script>
(function () {
  var body = document.body;
  var buttons = document.querySelectorAll('.mode-btn');
  var saved = null;
  try { saved = localStorage.getItem('hpmor-column-mode'); } catch (e) {}
  function apply(mode) {
    body.dataset.mode = mode;
    buttons.forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.mode === mode));
    });
    try { localStorage.setItem('hpmor-column-mode', mode); } catch (e) {}
  }
  if (saved) apply(saved);
  buttons.forEach(function (b) {
    b.addEventListener('click', function () { apply(b.dataset.mode); });
  });
})();
</script>"""


def build_translated_chapter(n: int, src: dict, tr: dict, titles: dict[str, str]) -> str:
    validate_translation(src, tr)
    is_machine = tr.get("translation") == "machine"
    by_n = {p["n"]: p for p in src["paragraphs"]}
    rows = []
    for sec in tr["sections"]:
        sid = sec["id"]
        en_cells = "".join(en_paragraph(by_n[pn]["html"]) for pn in sec["paras"])
        fa_cells = "".join(fa_paragraph(t) for t in sec["translation_fa"])
        rows.append(
            f'<tr id="sec-{sid}">'
            f'<td class="sec" data-label="بخش"><a class="sec-id" href="#sec-{sid}">§{fa_num(sid)}</a></td>'
            f'<td class="en verbatim col-en" dir="ltr" lang="en" data-label="۱. متن اصلی انگلیسی">{en_cells}</td>'
            f'<td class="fa trans col-fa" dir="rtl" lang="fa" data-label="۲. ترجمهٔ فارسی">{fa_cells}</td>'
            f'<td class="en summary col-en" dir="ltr" lang="en" data-label="۳. خلاصهٔ انگلیسی">{plain_summary(sec["summary_en"])}</td>'
            f'<td class="fa summary col-fa" dir="rtl" lang="fa" data-label="۴. خلاصهٔ فارسی">{plain_summary(sec["summary_fa"])}</td>'
            "</tr>"
        )

    if is_machine:
        kicker = f"فصل {fa_num(n)} از {fa_num(TOTAL)} · ترجمهٔ ماشینی — نیازمند ویرایش"
        notice = f"""<div class="notice machine-note">
      <p><strong>این فصل با ترجمهٔ ماشینی آماده شده و هنوز ویرایش انسانی نشده است.</strong> متن برای خواندن و مقایسه در دسترس است، اما ممکن است برخی جمله‌ها ناهموار یا نادرست باشند. فصل‌های ۱ و ۲ ترجمهٔ دستی هستند.</p>
      <p>برای اصلاح، فایل <code>data/ch{n:03d}.json</code> را در <a href="{REPO_URL}" rel="noopener">مخزن GitHub</a> ویرایش کنید و عبارت <code>"translation": "machine"</code> را بردارید.</p>
    </div>"""
    else:
        kicker = f"فصل {fa_num(n)} از {fa_num(TOTAL)} · ترجمه‌شده"
        notice = """<div class="notice">این صفحه متن اصلی انگلیسی را کنار ترجمه و خلاصه‌های فارسی می‌گذارد تا هم خواندن و هم مقایسه آسان باشد. اگر ستون‌های انگلیسی را نمی‌خواهید، از دکمهٔ «فقط فارسی» استفاده کنید.</div>"""

    body = f"""<main class="wrap">
  <div class="chapter-head">
    <p class="kicker">{kicker}</p>
    <h1>{esc(tr["title_fa"])}</h1>
    <p class="latin">Chapter {n}: {esc(src["title"])}</p>
    <div class="chapter-meta">
      <span>{fa_num(len(src["paragraphs"]))} پاراگراف</span>
      <span>{fa_num(len(tr["sections"]))} بخش</span>
      <a href="https://hpmor.info/chapter/{n}/" rel="noopener">متن اصلی در hpmor.info ↗</a>
      <a href="index.html">همهٔ فصل‌ها</a>
    </div>
  </div>
  {notice}
  {toolbar_html()}
  <div class="table-wrap">
    <table class="parallel">
      <colgroup><col class="c-sec"><col class="c-en"><col class="c-fa"><col class="c-sum"><col class="c-fasum"></colgroup>
      <thead><tr>
        <th scope="col">§</th>
        <th scope="col">۱. متن اصلی انگلیسی</th>
        <th scope="col" dir="rtl" lang="fa">۲. ترجمهٔ فارسی</th>
        <th scope="col">۳. خلاصهٔ انگلیسی</th>
        <th scope="col" dir="rtl" lang="fa">۴. خلاصهٔ فارسی</th>
      </tr></thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </div>
  {chapter_nav(n, titles)}
</main>"""
    return page_shell(
        f"فصل {fa_num(n)}: {tr['title_fa']} | {SITE_NAME}",
        body,
        active="index",
        script=MODE_SCRIPT,
    )


def build_source_chapter(n: int, src: dict, titles: dict[str, str]) -> str:
    rows = "".join(
        f'<tr id="p{p["n"]}"><td class="n">{fa_num(p["n"])}</td>'
        f'<td class="en" dir="ltr" lang="en">{en_paragraph(p["html"])}</td></tr>'
        for p in src["paragraphs"]
    )
    body = f"""<main class="wrap">
  <div class="chapter-head">
    <p class="kicker">فصل {fa_num(n)} از {fa_num(TOTAL)} · در انتظار ترجمه</p>
    <h1>{esc(titles[str(n)])}</h1>
    <p class="latin">Chapter {n}: {esc(src["title"])}</p>
    <div class="chapter-meta">
      <span>{fa_num(len(src["paragraphs"]))} پاراگراف</span>
      <a href="https://hpmor.info/chapter/{n}/" rel="noopener">متن اصلی در hpmor.info ↗</a>
      <a href="index.html">همهٔ فصل‌ها</a>
    </div>
  </div>
  <div class="source-note">
    <p><strong>ترجمهٔ فارسی این فصل هنوز آماده نشده است.</strong> برای اینکه سایت از همان ابتدا کامل باشد، متن اصلی انگلیسی در ادامه آمده است. ترجمه‌ها به‌ترتیب فصل اضافه می‌شوند.</p>
    <p>اگر می‌خواهید در ترجمه کمک کنید، به <a href="{REPO_URL}" rel="noopener">مخزن GitHub</a> سر بزنید.</p>
  </div>
  <div class="table-wrap" style="padding:.4rem 1rem">
    <table class="source">{rows}</table>
  </div>
  {chapter_nav(n, titles)}
</main>"""
    return page_shell(
        f"فصل {fa_num(n)}: {titles[str(n)]} | {SITE_NAME}",
        body,
        active="index",
    )


def build_index(titles: dict[str, str], hand: set[int], machine: set[int]) -> str:
    cards = []
    for n in range(1, TOTAL + 1):
        src = load_source(n)
        if n in hand:
            status = "done"
            badge = '<span class="badge done">ترجمهٔ دستی</span>'
            foot_label = "خواندن ترجمه"
        elif n in machine:
            status = "machine"
            badge = '<span class="badge machine">ترجمهٔ ماشینی</span>'
            foot_label = "خواندن ترجمه"
        else:
            status = "pending"
            badge = '<span class="badge pending">فقط انگلیسی</span>'
            foot_label = "متن انگلیسی"
        search_blob = f"{n} {titles[str(n)]} {src['title']}".lower()
        cards.append(
            f'<li class="chapter-card" data-status="{status}" data-search="{esc(search_blob)}">'
            f'<span class="num">فصل {fa_num(n)}</span>'
            f'<span class="fa-title">{esc(titles[str(n)])}</span>'
            f'<span class="en-title">Chapter {n}: {esc(src["title"])}</span>'
            f'<span class="card-foot"><span>{badge}</span><span>{foot_label} ←</span></span>'
            f'<a class="overlay" href="{chapter_url(n)}" aria-label="فصل {fa_num(n)}: {esc(titles[str(n)])}"></a>'
            "</li>"
        )

    done_count = len(hand | machine)
    percent = round(done_count * 100 / TOTAL, 1)
    body = f"""<main class="wrap">
  <section class="hero">
    <p class="kicker">پروژهٔ ترجمهٔ فارسی · نسخهٔ موازی</p>
    <h1>هری پاتر و روش‌های عقلانیت</h1>
    <p class="latin">Harry Potter and the Methods of Rationality — Eliezer Yudkowsky</p>
    <p class="lead">متن اصلی انگلیسی، ترجمهٔ فارسی، خلاصهٔ انگلیسی و خلاصهٔ فارسی، کنار هم و بخش‌به‌بخش. یک ابزار مطالعه برای خواندن دقیق‌تر و مقایسهٔ زبان اصلی با ترجمه.</p>
    <div class="hero-actions">
      <a class="btn primary" href="{chapter_url(1)}">شروع از فصل ۱</a>
      <a class="btn" href="about.html">دربارهٔ روش کار</a>
    </div>
  </section>

  <section class="panel progress-panel" aria-label="پیشرفت ترجمه">
    <div>
      <div class="label">پیشرفت ترجمه</div>
      <div class="hint">{fa_num(len(hand))} فصل ترجمهٔ دستی · {fa_num(len(machine))} فصل ترجمهٔ ماشینی (نیازمند ویرایش) · {fa_num(TOTAL - done_count)} فصل فقط انگلیسی</div>
      <div class="progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="122" aria-valuenow="{done_count}">
        <div class="progress-fill" style="width:{percent}%"></div>
      </div>
    </div>
    <div class="progress-number">{fa_num(done_count)} از {fa_num(TOTAL)} فصل</div>
  </section>

  <div class="notice">این ترجمه غیررسمی و غیرتجاری است. متن اصلی نوشتهٔ الیزر یودکوفسکی است و در <a href="https://hpmor.com/" rel="noopener">hpmor.com</a> رایگان منتشر شده. هری پاتر © جی.کی. رولینگ.</div>

  <section aria-label="فهرست فصل‌ها">
    <div class="list-toolbar">
      <label class="search">
        <span aria-hidden="true">⌕</span>
        <input id="chapter-search" type="search" placeholder="جستجوی شماره یا عنوان فصل…" autocomplete="off">
      </label>
      <div class="filters" role="group" aria-label="صافی وضعیت">
        <button type="button" data-filter="all" aria-pressed="true">همه</button>
        <button type="button" data-filter="done" aria-pressed="false">ترجمهٔ دستی</button>
        <button type="button" data-filter="machine" aria-pressed="false">ترجمهٔ ماشینی</button>
        <button type="button" data-filter="pending" aria-pressed="false">فقط انگلیسی</button>
      </div>
    </div>
    <ol class="chapter-grid" id="chapter-list">
      {''.join(cards)}
    </ol>
    <p id="no-results" style="display:none;color:var(--ink-soft)">فصلی با این جستجو پیدا نشد.</p>
  </section>
</main>"""

    script = """<script>
(function () {
  var cards = Array.prototype.slice.call(document.querySelectorAll('.chapter-card'));
  var input = document.getElementById('chapter-search');
  var filters = document.querySelectorAll('.filters button');
  var empty = document.getElementById('no-results');
  var status = 'all';
  function update() {
    var q = (input.value || '').trim().toLowerCase();
    var visible = 0;
    cards.forEach(function (card) {
      var okStatus = status === 'all' || card.dataset.status === status;
      var okText = !q || card.dataset.search.indexOf(q) !== -1;
      var show = okStatus && okText;
      card.style.display = show ? '' : 'none';
      if (show) visible++;
    });
    empty.style.display = visible ? 'none' : '';
  }
  input.addEventListener('input', update);
  filters.forEach(function (b) {
    b.addEventListener('click', function () {
      status = b.dataset.filter;
      filters.forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      update();
    });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === '/' && document.activeElement !== input) {
      e.preventDefault(); input.focus();
    }
  });
})();
</script>"""
    return page_shell(
        f"{SITE_NAME} — {SITE_TAGLINE}",
        body,
        active="index",
        script=script,
    )


def build_about(titles: dict[str, str], hand: set[int], machine: set[int]) -> str:
    done_count = len(hand | machine)
    body = f"""<main class="wrap">
  <section class="hero" style="padding-bottom:1rem">
    <p class="kicker">دربارهٔ پروژه</p>
    <h1>چهار ستون، یک کتاب</h1>
    <p class="lead">این سایت برای خواندن دقیق <em>هری پاتر و روش‌های عقلانیت</em> به فارسی ساخته شده است. هر بخش از فصل در چهار ستون نمایش داده می‌شود تا بتوانید متن اصلی، ترجمه، خلاصهٔ انگلیسی و خلاصهٔ فارسی را کنار هم ببینید.</p>
  </section>

  <div class="panel prose">
    <h2>ستون‌ها</h2>
    <ul>
      <li><strong>۱. متن اصلی انگلیسی:</strong> متن کامل و بدون تغییرِ داستان، برای مقایسه و بازبینی.</li>
      <li><strong>۲. ترجمهٔ فارسی:</strong> ترجمهٔ نزدیک به متن، با حفظ لحن و اصطلاحات داستان.</li>
      <li><strong>۳. خلاصهٔ انگلیسی:</strong> یک یا دو جمله که اتفاق اصلی همان بخش را به انگلیسی می‌گوید.</li>
      <li><strong>۴. خلاصهٔ فارسی:</strong> همان بخش، فشرده و به فارسی.</li>
    </ul>

    <h2>روش کار</h2>
    <p>متن انگلیسی از آینهٔ حاشیه‌نویسی‌شدهٔ <a href="https://hpmor.info/" rel="noopener">hpmor.info</a> گرفته می‌شود و پاراگراف‌به‌پاراگراف نگهداری می‌شود. هر فصل به بخش‌های کوتاه تقسیم می‌شود تا جدول خوانا بماند. ترجمه‌ها در فایل‌های JSON کنار متن اصلی ذخیره می‌شوند و سایت با یک اسکریپت پایتون ساخته می‌شود.</p>
    <p>در حال حاضر <strong>{fa_num(done_count)} فصل از {fa_num(TOTAL)} فصل</strong> به فارسی خواندنی است: {fa_num(len(hand))} فصل ترجمهٔ دستی و {fa_num(len(machine))} فصل ترجمهٔ ماشینی که هنوز ویرایش انسانی نشده است.</p>

    <h2>وضعیت ترجمه</h2>
    <p>فصل‌های ۱ و ۲ با دقت و به‌صورت دستی ترجمه شده‌اند. بقیهٔ فصل‌ها با ابزار ترجمهٔ ماشینی آماده شده‌اند تا کل کتاب از همین حالا قابل خواندن باشد؛ این فصل‌ها در فهرست با برچسب «ترجمهٔ ماشینی» مشخص شده‌اند و در بالای هر صفحه هم یادآوری شده است. هر فصل ماشینی را می‌توان بعداً با ویرایش فایل <code>data/chNNN.json</code> به ترجمهٔ انسانی ارتقا داد.</p>

    <h2>مشارکت</h2>
    <p>مخزن پروژه در <a href="{REPO_URL}" rel="noopener">github.com/hamidmdh/hpmor</a> است. برای افزودن یا اصلاح ترجمه، فایل <code>data/chNNN.json</code> را ویرایش کنید و سپس <code>python3 scripts/build.py</code> را اجرا کنید. اسکریپت <code>python3 scripts/verify.py</code> پوشش پاراگراف‌ها و کامل بودن ترجمه را بررسی می‌کند.</p>

    <h2>حق نشر و اجازه</h2>
    <p>این یک ترجمهٔ غیررسمی، رایگان و غیرتجاری است. <em>Harry Potter and the Methods of Rationality</em> نوشتهٔ الیزر یودکوفسکی است و متن اصلی به‌صورت رایگان در <a href="https://hpmor.com/" rel="noopener">hpmor.com</a> منتشر شده است. دنیای هری پاتر و شخصیت‌های آن متعلق به جی.کی. رولینگ است. این پروژه هیچ ادعای مالکیت یا وابستگی رسمی ندارد.</p>
    <p>اگر صاحب حق هستید و به این پروژه اعتراض دارید، از طریق مخزن GitHub اطلاع دهید تا محتوای مربوط حذف شود.</p>

    <h2>قدردانی</h2>
    <p>از الیزر یودکوفسکی برای نوشتن این داستان، از گردانندگان <a href="https://hpmor.info/" rel="noopener">hpmor.info</a> برای نگهداری متن و حاشیه‌ها، و از همهٔ مترجمان و خوانندگانی که این مسیر را زنده نگه داشته‌اند سپاسگزاریم.</p>
  </div>
</main>"""
    return page_shell(f"دربارهٔ پروژه | {SITE_NAME}", body, active="about")


def main() -> int:
    titles = load_titles()
    hand: set[int] = set()
    machine: set[int] = set()
    built = 0
    for n in range(1, TOTAL + 1):
        src = load_source(n)
        if translation_path(n).exists():
            tr = load_json(translation_path(n))
            page = build_translated_chapter(n, src, tr, titles)
            if tr.get("translation") == "machine":
                machine.add(n)
            else:
                hand.add(n)
        else:
            page = build_source_chapter(n, src, titles)
        (ROOT / chapter_url(n)).write_text(page, encoding="utf-8")
        built += 1

    (ROOT / "index.html").write_text(build_index(titles, hand, machine), encoding="utf-8")
    (ROOT / "about.html").write_text(build_about(titles, hand, machine), encoding="utf-8")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")

    print(f"built {built} chapter pages, index.html, about.html")
    print(f"hand-translated: {sorted(hand)} ({len(hand)}/{TOTAL})")
    print(f"machine-translated: {len(machine)}/{TOTAL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
