#!/usr/bin/env python3
"""Inline sidebar.html into every page — single source of truth, zero runtime cost.

sidebar.html is the ONE file you edit. Run this to bake its contents into each
page so the pages are fully self-contained (work over file:// and on GitHub Pages,
no fetch, no flash, no cache-skew):

    python3 sync-sidebar.py

Each page carries a mount:  <aside class="sidebar" data-page="NAME">...</aside>
This fills that mount with the sidebar and marks the matching nav link active.
Re-running is safe (idempotent) — it always rebuilds the block from sidebar.html.
"""
import re, glob

SRC = "sidebar.html"
MOUNT_RE = re.compile(r'<aside class="sidebar" data-page="([a-z]+)">.*?</aside>', re.DOTALL)


def inner_sidebar():
    html = open(SRC, encoding="utf-8").read()
    # drop the leading "edit this file" HTML comment, if present
    html = re.sub(r'^\s*<!--.*?-->\s*', '', html, count=1, flags=re.DOTALL)
    return html.strip("\n")


def build_block(page, inner):
    active = inner.replace(
        f'<a class="nav-link" data-page="{page}"',
        f'<a class="nav-link active" data-page="{page}"', 1)
    body = "\n".join(("    " + ln) if ln.strip() else ln for ln in active.splitlines())
    return f'<aside class="sidebar" data-page="{page}">\n{body}\n  </aside>'


def sync_file(path, inner):
    s = open(path, encoding="utf-8").read()
    new, n = MOUNT_RE.subn(lambda m: build_block(m.group(1), inner), s)
    if n and new != s:
        open(path, "w", encoding="utf-8").write(new)
        return "updated", n
    return ("ok", n) if n else ("skip", 0)


def main():
    inner = inner_sidebar()
    total = 0
    for path in sorted(glob.glob("*.html")):
        if path == SRC:
            continue
        state, n = sync_file(path, inner)
        if n:
            total += n
            print(f"  {state:8} {path}")
    print(f"Done — {total} page(s) synced from {SRC}." if total
          else "No sidebar mounts found (look for <aside class=\"sidebar\" data-page=\"…\">).")


if __name__ == "__main__":
    main()
