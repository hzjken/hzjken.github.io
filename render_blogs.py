#!/usr/bin/env python3
"""Blog engine — turn files in blogs/ into rendered post pages + list + teasers.

Drop one file per post in blogs/:
  - <slug>.md   : YAML-ish frontmatter (--- ... ---) then Markdown  -> inline article
  - <slug>.html : frontmatter in a leading <!-- ... --> comment then a standalone
                  HTML document -> embedded in the post via <iframe>

Frontmatter fields: title, date (YYYY-MM-DD), tags (comma-separated), description.

Running this (CI does it automatically; run it yourself to preview):
  - writes <slug>.html for every post (the article page)
  - copies each .html post's standalone doc to embeds/<slug>.html (iframe source)
  - fills the post list + tag filters on blogs.html  (between the marker comments)
  - fills "Latest writing" on index.html with the newest 3 posts
Operates on the current directory by default, or on the dir passed as argv[1].
Safe to re-run: it only rewrites content between the <!--X:START-->/<!--X:END--> markers.
"""
import sys, os, re, glob, html
from datetime import datetime

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
<title>{title} — Ken Huang</title>
<meta name="description" content="{desc}">
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
        <span class="fmt"><i></i>{fmt}</span>
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

    # per-post pages (+ embeds for html posts)
    for p in posts:
        cat = p["tags"][0] if p["tags"] else "Note"
        tags_foot = (f'      <div class="tags-foot">{chips(p["tags"])}</div>\n'
                     if p["tags"] else "")
        if p["kind"] == "md":
            body = render_markdown(p["raw"])
            wide, fmt = "", "Markdown"
        else:
            os.makedirs(os.path.join(BASE, "embeds"), exist_ok=True)
            open(os.path.join(BASE, "embeds", p["slug"] + ".html"), "w",
                 encoding="utf-8").write(p["raw"])
            body = (f'      <figure style="margin:8px 0 0;width:100%">\n'
                    f'        <iframe class="embed-frame" src="embeds/{p["slug"]}.html" '
                    f'title="{esc(p["title"])}" scrolling="no" '
                    f'style="width:100%;height:1400px;"></iframe>\n      </figure>')
            wide, fmt = " wide", "HTML embed"
        page = HEAD.format(title=esc(p["title"]), desc=esc(p.get("description", "")),
                           wide=wide, cat=esc(cat), date=fmt_date(p["date"]),
                           mins=p["mins"], fmt=fmt, body=body, tags_foot=tags_foot)
        open(os.path.join(BASE, p["slug"] + ".html"), "w", encoding="utf-8").write(page)

    # blog list rows + tag filters
    rows = []
    seen_tags = []
    for i, p in enumerate(posts, 1):
        cat = p["tags"][0] if p["tags"] else "Note"
        for t in p["tags"]:
            if t not in seen_tags:
                seen_tags.append(t)
        data_title = esc((p["title"] + " " + " ".join(p["tags"])).lower())
        rows.append(
            f'\n      <a class="post-row" href="{p["slug"]}.html" '
            f'data-tags="{esc(" ".join(p["tags"]))}" data-title="{data_title}">\n'
            f'        <span class="num">{i:02d}</span>\n'
            f'        <div>\n'
            f'          <div class="meta"><span>{fmt_date(p["date"])}</span><span>·</span>'
            f'<span>{esc(cat)}</span><span>·</span><span>{p["mins"]} min</span></div>\n'
            f'          <h3>{esc(p["title"])}</h3>\n'
            f'          <p>{esc(p.get("description", ""))}</p>\n'
            f'        </div>\n      </a>')
    filters = '\n      <span class="chip clickable active" data-tag="all">All</span>' + \
        "".join(f'\n      <span class="chip clickable" data-tag="{esc(t)}">{esc(t)}</span>'
                for t in seen_tags) + "\n    "
    posts_html = "".join(rows) + "\n    "

    blogs_path = os.path.join(BASE, "blogs.html")
    page = open(blogs_path, encoding="utf-8").read()
    page = inject(page, "FILTERS", filters)
    page = inject(page, "POSTS", posts_html)
    open(blogs_path, "w", encoding="utf-8").write(page)

    # latest writing on the about page (newest 3)
    teasers = []
    for p in posts[:3]:
        teasers.append(
            f'\n    <a class="teaser" href="{p["slug"]}.html">\n'
            f'      <span class="date">{fmt_month(p["date"])}</span>\n'
            f'      <div><h3>{esc(p["title"])}</h3><p>{esc(p.get("description", ""))}</p></div>\n'
            f'    </a>')
    idx_path = os.path.join(BASE, "index.html")
    page = open(idx_path, encoding="utf-8").read()
    page = inject(page, "LATEST", "".join(teasers) + "\n  ")
    open(idx_path, "w", encoding="utf-8").write(page)

    print(f"Rendered {len(posts)} post(s): " + ", ".join(p["slug"] for p in posts))


if __name__ == "__main__":
    main()
