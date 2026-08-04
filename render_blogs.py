#!/usr/bin/env python3
"""Blog engine — turn files in blogs/ into rendered post pages + list + teasers.

Drop one file per post in blogs/:
  - <slug>.md   : YAML-ish frontmatter (--- ... ---) then Markdown  -> inline article
  - <slug>.html : frontmatter in a leading <!-- ... --> comment then a standalone
                  HTML document -> embedded in the post via <iframe>

Frontmatter fields: title, date (YYYY-MM-DD), tags (comma-separated), series, description.
Series are discovered automatically — a post's `series` value creates (or reuses) a
colored series tag + filter chip everywhere, so a new series needs no code changes.
A post without `series` falls back to "Notes".

Running this (CI does it automatically; run it yourself to preview):
  - writes <slug>.html for every post (the article page)
  - copies each .html post's standalone doc to embeds/<slug>.html (iframe source)
  - fills the series filters + post list on blogs.html (between the marker comments)
  - fills "Latest writing" and "What I write about" (series chips) on index.html
Operates on the current directory by default, or on the dir passed as argv[1].
Safe to re-run: it only rewrites content between the <!--X:START-->/<!--X:END--> markers.
"""
import sys, os, re, glob, html, json, zlib
from datetime import datetime

SITE = "https://hzjken.dev"
AUTHOR = "Ken Huang"
DEFAULT_SERIES = "Notes"

# Fixed palette; a series' color is picked by hashing its name, so colors stay
# stable across runs and when new series appear (crc32 is deterministic).
SERIES_PALETTE = ["#0ea5e9", "#f59e0b", "#10b981", "#8b5cf6", "#f43f5e",
                  "#14b8a6", "#6366f1", "#eab308"]

try:
    import markdown
    from markdown.treeprocessors import Treeprocessor
    from markdown.extensions import Extension
except ImportError:
    sys.exit("render_blogs.py needs the 'markdown' package:  pip install markdown")

BASE = sys.argv[1] if len(sys.argv) > 1 else "."
BLOGS = os.path.join(BASE, "blogs")

HEAD = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<title>{title} — {author}</title>
<meta name="description" content="{desc}">
<meta name="author" content="{author}">
<meta name="robots" content="index,follow">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{author}">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canonical}">
<meta property="article:published_time" content="{iso_date}">
<meta property="article:modified_time" content="{iso_modified}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{og_title}">
<meta name="twitter:description" content="{desc}">
{jsonld}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="styles.css">
<script src="theme.js"></script>
</head>
<body>
<div class="layout">

  <aside class="sidebar" data-page="blog"></aside>

  <main class="main reading">
    <article class="article{wide}">
      <a class="back-link" href="blogs.html">← All posts</a>
      <div class="post-meta"><span class="cat">{cat}</span><span>·</span><span>{date}</span><span>·</span><span>{mins} min read</span></div>
      <h1>{title}</h1>

      <div class="byline">
        <div class="av"><img src="assets/ken-avatar.jpg" alt="Ken Huang"></div>
        <div class="who"><b>Ken Huang</b><span>AI Engineer</span></div>
        {series_pill}
      </div>

{body}
{tags_foot}
    </article>
  </main>

</div>
</body>
</html>
"""


# --- Markdown -> HTML, with the design's classes -----------------------------
class _Prose(Treeprocessor):
    """Give top-level paragraphs the .prose class (first one .prose first)."""
    def run(self, root):
        first = True
        for el in list(root):
            if el.tag == "p":
                el.set("class", "prose first" if first else "prose")
                first = False
        return root


class _ProseExt(Extension):
    def extendMarkdown(self, md):
        md.treeprocessors.register(_Prose(md), "prose_classes", 5)


def wrap_codeblocks(h):
    """Wrap bare <pre><code> in the .codeblock shell (traffic-light header)."""
    def repl(m):
        lang = m.group(1) or "code"
        head = ('<div class="code-head">'
                '<span class="d" style="background:#ef6b5e"></span>'
                '<span class="d" style="background:#f6be4f"></span>'
                '<span class="d" style="background:#61c454"></span>'
                f'<span class="name">{html.escape(lang)}</span></div>')
        return f'<div class="codeblock">{head}<pre><code>{m.group(2)}</code></pre></div>'
    return re.sub(r'<pre><code(?:\s+class="language-([^"]+)")?>(.*?)</code></pre>',
                  repl, h, flags=re.DOTALL)


def render_markdown(text):
    md = markdown.Markdown(extensions=["fenced_code", "tables", _ProseExt()])
    return wrap_codeblocks(md.convert(text))


# --- frontmatter parsing -----------------------------------------------------
def parse_meta(lines):
    meta = {}
    for line in lines:
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip()
    meta["tags"] = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
    return meta


def load_md(path):
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"^\s*---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.DOTALL)
    if not m:
        sys.exit(f"{path}: missing '---' frontmatter block")
    meta = parse_meta(m.group(1).splitlines())
    return meta, m.group(2), "md"


def load_html(path):
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"^\s*<!--(.*?)-->\s*(.*)$", raw, re.DOTALL)
    if not m:
        sys.exit(f"{path}: missing leading <!-- frontmatter --> comment")
    meta = parse_meta(m.group(1).splitlines())
    return meta, m.group(2).strip(), "html"


# --- helpers -----------------------------------------------------------------
def fmt_date(s):
    d = datetime.strptime(s, "%Y-%m-%d")
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def fmt_month(s):
    d = datetime.strptime(s, "%Y-%m-%d")
    return f"{d.strftime('%b')} {d.year}"


def read_min(text):
    text = re.sub(r"<(style|script)\b[^>]*>.*?</\1>", " ", text, flags=re.DOTALL | re.I)
    words = len(re.sub(r"<[^>]+>", " ", text).split())
    return max(1, round(words / 200))


def esc(s):
    return html.escape(s or "", quote=True)


def chips(tags):
    return "".join(f'<span class="chip">{esc(t)}</span>' for t in tags)


# --- series helpers ----------------------------------------------------------
def series_name(p):
    return (p.get("series") or DEFAULT_SERIES).strip() or DEFAULT_SERIES


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.strip().lower()).strip("-")


def series_color(name):
    return SERIES_PALETTE[zlib.crc32(name.encode("utf-8")) % len(SERIES_PALETTE)]


def series_tag(name):
    """Colored series pill; --sc drives the hue, theme-adaptive via color-mix."""
    return (f'<span class="series-tag" style="--sc:{series_color(name)}">'
            f'{esc(name)}</span>')


def series_chip(name, active=False):
    """Colored clickable chip for the blogs.html series filter row."""
    cls = "series-chip" + (" active" if active else "")
    return (f'<span class="{cls}" data-series="{slugify(name)}" '
            f'style="--sc:{series_color(name)}">{esc(name)}</span>')


def inject(page, name, content):
    s, e = f"<!--{name}:START-->", f"<!--{name}:END-->"
    return re.sub(re.escape(s) + r".*?" + re.escape(e), s + content + e, page, flags=re.DOTALL)


# --- build -------------------------------------------------------------------
def main():
    if not os.path.isdir(BLOGS):
        sys.exit(f"No blogs/ folder at {os.path.abspath(BLOGS)}")

    posts = []
    for path in sorted(glob.glob(os.path.join(BLOGS, "*.md")) +
                       glob.glob(os.path.join(BLOGS, "*.html"))):
        slug = os.path.splitext(os.path.basename(path))[0]
        if slug in ("index", "blogs", "projects", "sidebar", "styles", "theme"):
            sys.exit(f"{path}: '{slug}' is a reserved name — rename the file")
        if path.endswith(".md"):
            meta, raw, kind = load_md(path)
        else:
            meta, raw, kind = load_html(path)
        for req in ("title", "date"):
            if not meta.get(req):
                sys.exit(f"{path}: frontmatter missing '{req}'")
        meta.update(slug=slug, kind=kind, raw=raw)
        meta["mins"] = read_min(raw)
        posts.append(meta)

    posts.sort(key=lambda p: (p["date"], p["title"]), reverse=True)

    # series in first-appearance order (posts sorted by date desc)
    seen_series = []
    for p in posts:
        s = series_name(p)
        if s not in seen_series:
            seen_series.append(s)

    # per-post pages (+ embeds for html posts)
    for p in posts:
        cat = p["tags"][0] if p["tags"] else "Note"
        tags_foot = (f'      <div class="tags-foot">{chips(p["tags"])}</div>\n'
                     if p["tags"] else "")
        canonical = f"{SITE}/{p['slug']}.html"
        iso_date = p["date"]
        iso_modified = p.get("updated") or p["date"]
        jsonld = (
            '<script type="application/ld+json">'
            + json.dumps({
                "@context": "https://schema.org",
                "@type": "BlogPosting",
                "headline": p["title"],
                "description": p.get("description", ""),
                "datePublished": iso_date,
                "dateModified": iso_modified,
                "inLanguage": "en",
                "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
                "url": canonical,
                "author": {"@type": "Person", "name": AUTHOR, "url": SITE + "/"},
                "publisher": {"@type": "Person", "name": AUTHOR, "url": SITE + "/"},
            }, ensure_ascii=False)
            + '</script>'
        )
        if p["kind"] == "md":
            body = render_markdown(p["raw"])
            wide = ""
        else:
            os.makedirs(os.path.join(BASE, "embeds"), exist_ok=True)
            raw = p["raw"]
            head_idx = raw.find("<head>")
            if head_idx != -1:
                head_idx += len("<head>")
                raw = (raw[:head_idx]
                       + '\n<meta name="robots" content="noindex,follow">'
                       + raw[head_idx:])
            open(os.path.join(BASE, "embeds", p["slug"] + ".html"), "w",
                 encoding="utf-8").write(raw)
            body = (f'      <figure style="margin:8px 0 0;width:100%">\n'
                    f'        <iframe class="embed-frame" src="embeds/{p["slug"]}.html" '
                    f'title="{esc(p["title"])}" scrolling="no" '
                    f'style="width:100%;height:1400px;"></iframe>\n      </figure>')
            wide = " wide"
        page = HEAD.format(title=esc(p["title"]), author=AUTHOR,
                           desc=esc(p.get("description", "")), canonical=esc(canonical),
                           og_title=esc(p["title"]), iso_date=iso_date,
                           iso_modified=iso_modified, jsonld=jsonld,
                           wide=wide, cat=esc(cat), date=fmt_date(p["date"]),
                           mins=p["mins"], series_pill=series_tag(series_name(p)),
                           body=body, tags_foot=tags_foot)
        open(os.path.join(BASE, p["slug"] + ".html"), "w", encoding="utf-8").write(page)

    # sitemap.xml + robots.txt
    today = datetime.today().strftime("%Y-%m-%d")
    urls = [
        (SITE + "/", today, "daily", "1.0"),
        (SITE + "/blogs.html", today, "weekly", "0.9"),
        (SITE + "/projects.html", today, "monthly", "0.6"),
    ]
    for p in posts:
        urls.append((f"{SITE}/{p['slug']}.html", p["date"], "monthly", "0.8"))
    locs = "".join(
        f'  <url><loc>{esc(u)}</loc><lastmod>{d}</lastmod>'
        f'<changefreq>{c}</changefreq><priority>{pr}</priority></url>\n'
        for u, d, c, pr in urls)
    sitemap = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
               + locs + '</urlset>\n')
    open(os.path.join(BASE, "sitemap.xml"), "w", encoding="utf-8").write(sitemap)
    robots = "User-agent: *\nAllow: /\n\nSitemap: " + SITE + "/sitemap.xml\n"
    open(os.path.join(BASE, "robots.txt"), "w", encoding="utf-8").write(robots)

    # blog list rows + series filters (no clickable tag chips — series is the
    # grouping mechanism; tags still power the search via data-title/data-tags)
    rows = []
    for i, p in enumerate(posts, 1):
        cat = p["tags"][0] if p["tags"] else "Note"
        series = series_name(p)
        data_title = esc((p["title"] + " " + " ".join(p["tags"]) + " " + series).lower())
        rows.append(
            f'\n      <a class="post-row" href="{p["slug"]}.html" '
            f'data-tags="{esc(" ".join(p["tags"]))}" data-series="{slugify(series)}" '
            f'data-title="{data_title}">\n'
            f'        <span class="num">{i:02d}</span>\n'
            f'        <div>\n'
            f'          <div class="meta"><span>{fmt_date(p["date"])}</span><span>·</span>'
            f'<span>{esc(cat)}</span><span>·</span><span>{p["mins"]} min</span></div>\n'
            f'          <h3>{esc(p["title"])} {series_tag(series)}</h3>\n'
            f'          <p>{esc(p.get("description", ""))}</p>\n'
            f'        </div>\n      </a>')
    series_filters = ('\n      <span class="series-chip active" data-series="all" style="--sc:#8b93a1">All</span>'
                      + "".join("\n      " + series_chip(s) for s in seen_series) + "\n    ")
    posts_html = "".join(rows) + "\n    "

    blogs_path = os.path.join(BASE, "blogs.html")
    page = open(blogs_path, encoding="utf-8").read()
    page = inject(page, "SERIESFILTERS", series_filters)
    page = inject(page, "POSTS", posts_html)
    open(blogs_path, "w", encoding="utf-8").write(page)

    # latest writing on the about page (newest 3) + "What I write about" series chips
    teasers = []
    for p in posts[:3]:
        series = series_name(p)
        teasers.append(
            f'\n    <a class="teaser" href="{p["slug"]}.html">\n'
            f'      <span class="date">{fmt_month(p["date"])}</span>\n'
            f'      <div><h3>{esc(p["title"])} {series_tag(series)}</h3>'
            f'<p>{esc(p.get("description", ""))}</p></div>\n'
            f'    </a>')
    topics = "".join(
        f'\n      <a class="series-chip" href="blogs.html?series={slugify(s)}" '
        f'style="--sc:{series_color(s)}">{esc(s)}</a>'
        for s in seen_series) + "\n    "
    idx_path = os.path.join(BASE, "index.html")
    page = open(idx_path, encoding="utf-8").read()
    page = inject(page, "SERIES", topics)
    page = inject(page, "LATEST", "".join(teasers) + "\n  ")
    open(idx_path, "w", encoding="utf-8").write(page)

    print(f"Rendered {len(posts)} post(s): " + ", ".join(p["slug"] for p in posts))


if __name__ == "__main__":
    main()
