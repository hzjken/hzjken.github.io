# Ken Huang — personal site

Static personal + blog site — plain HTML/CSS/JS. The only build step is a tiny script that
inlines the shared sidebar; GitHub Actions runs it automatically on deploy.

## Files
- `index.html` — About me (home)
- `blogs.html` — post list with live search + tag filter (rows generated from `blogs/`)
- `projects.html` — GitHub-style project cards
- `blogs/` — **your posts** — one `.md` or `.html` file per post (the only thing you edit to publish)
- `render_blogs.py` — turns `blogs/` into post pages + the list + the about-page teasers
- `sidebar.html` — the shared sidebar (brand, socials, nav, theme toggle) — **edit this ONE file**
- `sync-sidebar.py` — inlines `sidebar.html` into every page (run by CI; run it yourself to preview)
- `styles.css` — all styling + light/dark tokens (blue accent)
- `theme.js` — persistent light/dark toggle + auto-sizing embeds
- `assets/` — avatar image + `favicon.svg` (the browser-tab / bookmark icon)
- `.github/workflows/pages.yml` — builds (render blogs + inline sidebar) and deploys to GitHub Pages

## The sidebar is shared (edit it in one place)
`sidebar.html` is the single source of truth. Each page keeps only a clean, empty mount —
`<aside class="sidebar" data-page="…"></aside>` (`about` / `blog` / `projects`). At deploy time
GitHub Actions runs `sync-sidebar.py`, which inlines `sidebar.html` into every mount and marks the
right nav link active. **Your source `.html` files stay clean; the deployed site is self-contained**
(no runtime fetch, no flash, no cache-skew blank sidebar).

To change your name, avatar, social links, or nav: **edit `sidebar.html`, commit, push.** Done.

### Previewing locally
Because the source pages have empty mounts, the sidebar only appears after the inline step. To see
it locally, run the same step the CI runs, then restore the clean mounts when done:

    python3 sync-sidebar.py       # fills the sidebars in place
    python3 -m http.server        # open http://localhost:8000
    git checkout -- '*.html'      # restore clean empty mounts before committing

(Or just push — CI deploys the inlined site.)

## Deploy to GitHub Pages
Deployment is automatic: every push to `main` triggers `.github/workflows/pages.yml`, which inlines
the sidebar and publishes to `https://hzjken.github.io/`. Pages is configured with
**Settings → Pages → Source: GitHub Actions**. No manual steps.

## Writing a blog post
Drop **one file** in `blogs/` — that's the whole workflow. On push, CI renders it into a full page,
adds it to the blog list, and updates "Latest writing" on the about page (newest 3, sorted by date).
No HTML boilerplate, no editing `blogs.html`/`index.html` by hand.

Two formats, both starting with frontmatter:

**Markdown** — `blogs/my-post.md` (rendered as a normal article):
```
---
title: My post title
date: 2026-07-10
tags: RAG, Evals
description: One-line summary shown in the list and teaser.
---

## A heading
Normal **markdown** — paragraphs, lists, > blockquotes, and ```fenced code```.
```

**HTML** — `blogs/my-widget.html` (a standalone HTML document embedded via `<iframe>`, for
interactive/visual posts). Same frontmatter, but in a leading comment:
```
<!--
title: My interactive explainer
date: 2026-07-10
tags: Engineering
description: A live, self-contained HTML explainer.
-->
<!DOCTYPE html> ...your standalone page... </html>
```

- Filename = URL slug (`my-post.md` → `my-post.html`). Avoid the reserved names
  `index`, `blogs`, `projects`, `sidebar`, `styles`, `theme`.
- Tag filter chips and read-time are generated automatically.
- Preview locally: `pip install markdown`, then `python3 render_blogs.py && python3 sync-sidebar.py`,
  open with a local server, and `git checkout -- . && git clean -fd` to discard the generated files.
  (Or just push — CI builds it.)
