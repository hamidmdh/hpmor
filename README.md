# HPMOR — Persian parallel translation

A static, four-column reading site for *Harry Potter and the Methods of
Rationality* by Eliezer Yudkowsky:

1. **Verbatim English** — the original paragraph, unchanged
2. **English summary** — one or two sentences per section
3. **Persian translation** — faithful, close to the original
4. **Persian summary** — the same section, condensed in Persian

The layout is inspired by
[hkalbasi/reading-helper](https://github.com/hkalbasi/reading-helper), but the
Persian translation and summaries here are produced for this project.

Live site (after Pages is enabled): `https://hamidmdh.github.io/hpmor/`

> GitHub Pages on a **private** repository requires a paid GitHub plan. On the
> free plan, make the repository public or deploy `_site/` to another static
> host (Cloudflare Pages, Netlify, etc.). The included workflow skips itself on
> private repos unless the repository variable `ENABLE_PAGES` is set to `true`.

## Status

- English source: **all 122 chapters** saved in `data/chNNN_source.json`
- Persian translation: **chapter 1** complete; chapters 2–122 pending
- The index lists every chapter; untranslated chapters show the English text
  and a notice until their translation is added

Progress is shown automatically on the home page.

## Repository layout

```
index.html                 generated chapter list + progress
about.html                 generated project/about page
chapter1.html … 122.html   generated pages
assets/styles.css          site styles
assets/favicon.svg
data/chNNN_source.json     English paragraphs (from hpmor.info)
data/chNNN.json            Persian translation for one chapter (optional)
data/titles_fa.json        Persian titles for all 122 chapters
scripts/fetch_chapters.py  download English source
scripts/scaffold_chapter.py create an empty translation skeleton
scripts/build.py           build all HTML pages
scripts/verify.py          validate data and translation coverage
scripts/package.py         copy publishable files to _site/
.github/workflows/pages.yml deploy to GitHub Pages
```

## Local commands

```bash
# Rebuild the whole site (uses committed data; no network needed)
python3 scripts/build.py
python3 scripts/verify.py

# Preview locally
python3 -m http.server 8000
# open http://localhost:8000/

# Re-fetch the English source (only if you need to refresh it)
python3 scripts/fetch_chapters.py          # all 122 chapters
python3 scripts/fetch_chapters.py 1 2 3    # selected chapters

# Start a new chapter translation
python3 scripts/scaffold_chapter.py 2
# then edit data/ch002.json, run build + verify
```

No third-party Python packages are required (standard library only).

## Translation data format

`data/ch001.json` is the model to copy. A chapter is split into short
**sections**; each section stores the paragraph numbers it covers, its two
summaries, and one Persian translation per paragraph:

```json
{
  "chapter": 1,
  "title": "A Day of Very Low Probability",
  "title_fa": "روزی با احتمال بسیار کم",
  "sections": [
    {
      "id": 1,
      "paras": [1, 2],
      "summary_en": "One or two sentences in English.",
      "translation_fa": ["ترجمهٔ پاراگراف اول.", "ترجمهٔ پاراگراف دوم."],
      "summary_fa": "یک یا دو جملهٔ فارسی."
    }
  ]
}
```

Rules enforced by `scripts/verify.py`:

- `paras` must cover every paragraph of the source exactly once, in order
- `translation_fa` must have exactly one non-empty string per paragraph
- `summary_en` and `summary_fa` must be non-empty
- `id` values must be unique within the chapter

The English column is always read directly from `data/chNNN_source.json`, so it
cannot drift from the translation file.

## Adding a translation

1. Run `python3 scripts/scaffold_chapter.py N` to create `data/chNNN.json`.
2. Translate each paragraph and write both summaries.
3. Run `python3 scripts/build.py && python3 scripts/verify.py`.
4. Commit `data/chNNN.json` together with the regenerated `chapterN.html`,
   `index.html`, and `about.html`.

Keep names and terms consistent with chapter 1: هری، پتونیا، مایکل، لیلی،
هاگوارتز، مک‌گوناگل، دامبلدور، اسنیپ، کویریل، مالفوی، هرمیون، ران، نویل.

## Attribution and license

This is an unofficial, free, non-commercial fan translation.

- *Harry Potter and the Methods of Rationality* © Eliezer Yudkowsky, published
  free at [hpmor.com](https://hpmor.com/)
- The Harry Potter world and characters © J.K. Rowling
- English source text mirrored from the annotated edition at
  [hpmor.info](https://hpmor.info/)

This project claims no ownership of the original work and is not affiliated
with or endorsed by the author or rights holders. If a rights holder objects,
open an issue in this repository and the affected content will be removed.
