#!/usr/bin/env python3
"""Import a standalone HTML article into the blog as a draft post.

Reusable for any article URL.

What it does, for any URL:
  1. Fetches the page HTML.
  2. Extracts <style>, <body>, and inline/CDN <script> blocks.
  3. Scopes ALL article CSS under .sr-article so it cannot leak into the
     blog shell (nav, footer, headings).
  4. Drops the article's own <h1> (the post template renders the title).
  5. Rewrites the Chart.js CDN reference to the vendored copy via the
     __ASSETS__ token, which build.py resolves per render context.
  6. Writes content/posts/<date>-<slug>.md with frontmatter, draft: true.

Usage:
  python3 scripts/import_article.py URL --date 2026-07-01 \
      [--slug my-slug] [--title "..."] [--author "Starchild Research"] \
      [--tags a,b,c] [--description "..."] [--publish]

Then: python3 build.py  (draft appears at /drafts/<slug>/ and in the
drafts preview index).
"""
from __future__ import annotations

import argparse
import re
import sys
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent.parent.parent))  # /data/workspace for core.*

CHART_CDN_RE = re.compile(
    r'<script\s+src=["\']https?://[^"\']*chart(?:\.umd)?(?:\.min)?\.js[^"\']*["\'][^>]*>\s*</script>',
    re.I,
)


def fetch(url: str) -> str:
    from core.http_client import proxied_get

    r = proxied_get(url, timeout=30)
    r.raise_for_status()
    # Servers that omit charset make requests default to ISO-8859-1,
    # garbling UTF-8 (★ -> â). Decode explicitly.
    if not r.encoding or r.encoding.lower() in ("iso-8859-1", "latin-1"):
        r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def scope_css(css: str, scope: str = ".sr-article") -> str:
    """Prefix every top-level selector with the scope class.

    Handles @media/@supports blocks (recurses into them), converts
    html/body/:root selectors to the scope itself, and leaves @keyframes
    and @font-face untouched.
    """
    out = []
    i = 0
    n = len(css)
    while i < n:
        # Skip whitespace / comments
        m = re.match(r"\s+|/\*[\s\S]*?\*/", css[i:])
        if m:
            out.append(m.group(0))
            i += m.end()
            continue
        # At-rule with a block
        if css[i] == "@":
            head_end = css.find("{", i)
            if head_end == -1:  # e.g. @import ...;
                semi = css.find(";", i)
                stop = semi + 1 if semi != -1 else n
                out.append(css[i:stop])
                i = stop
                continue
            head = css[i:head_end]
            depth = 1
            j = head_end + 1
            while j < n and depth:
                if css[j] == "{":
                    depth += 1
                elif css[j] == "}":
                    depth -= 1
                j += 1
            inner = css[head_end + 1 : j - 1]
            name = head.strip().split("(")[0].split()[0].lower()
            if name in ("@media", "@supports", "@container", "@layer"):
                out.append(head + "{" + scope_css(inner, scope) + "}")
            else:  # @keyframes, @font-face, @page: leave as-is
                out.append(css[i:j])
            i = j
            continue
        # Ordinary rule: selector { body }
        sel_end = css.find("{", i)
        if sel_end == -1:
            out.append(css[i:])
            break
        depth = 1
        j = sel_end + 1
        while j < n and depth:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
            j += 1
        selectors = css[i:sel_end]
        body = css[sel_end:j]
        scoped_sels = []
        for sel in selectors.split(","):
            s = sel.strip()
            if not s:
                continue
            # html / body / :root become the scope container itself
            s = re.sub(r"^(html|body|:root)\b", scope, s)
            if not s.startswith(scope):
                s = f"{scope} {s}"
            scoped_sels.append(s)
        out.append(", ".join(scoped_sels) + body)
        i = j
    return "".join(out)


def extract(html: str) -> dict:
    title_m = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", html, re.I)
    raw_title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip() if title_m else ""
    styles = re.findall(r"<style[^>]*>([\s\S]*?)</style>", html, re.I)
    body_m = re.search(r"<body[^>]*>([\s\S]*?)</body>", html, re.I)
    body = body_m.group(1) if body_m else html
    inline_scripts = [
        s for s in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)</script>", body + html, re.I)
        if s.strip()
    ]
    # De-dup (body + html overlap)
    seen, scripts = set(), []
    for s in inline_scripts:
        k = s.strip()[:200]
        if k not in seen:
            seen.add(k)
            scripts.append(s.strip())
    needs_chart = bool(CHART_CDN_RE.search(html)) or "new Chart(" in html
    # Remove scripts from body; they are re-emitted at the end
    body = re.sub(r"<script[\s\S]*?</script>", "", body, flags=re.I)
    # Drop the article's own h1 (post template renders the title)
    body = re.sub(r"<h1[^>]*>[\s\S]*?</h1>\s*", "", body, count=1, flags=re.I)
    return {
        "title": unescape(raw_title),
        "css": "\n".join(styles),
        "body": body.strip(),
        "scripts": scripts,
        "needs_chart": needs_chart,
    }


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)[:80]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--slug", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--author", default="Blog Team")
    ap.add_argument("--tags", default="")
    ap.add_argument("--description", default="")
    ap.add_argument("--publish", action="store_true", help="draft: false")
    args = ap.parse_args()

    html = fetch(args.url)
    ex = extract(html)
    title = args.title or ex["title"]
    if not title:
        raise SystemExit("no <h1> found; pass --title")
    slug = args.slug or slugify(title)
    desc = args.description or f"{title}."
    if len(desc) > 160:
        desc = desc[:157] + "..."
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    css = scope_css(ex["css"]) if ex["css"] else ""
    parts = [f"<!-- imported from {args.url} -->"]
    if css:
        parts.append(
            "<style>\n.sr-article { color: #151515; }\n"
            ".sr-article * { box-sizing: border-box; }\n"
            + css
            + "\n.sr-article canvas { max-width: 100%; }\n"
            # Blog-shell consistency: imported page-level chrome (body
            # background, margins) must not restyle the article container.
            # Appended last so it wins the cascade at equal specificity.
            + ".sr-article { background: transparent; margin: 0; padding: 0; "
            + "font-family: inherit; font-size: inherit; line-height: inherit; }\n"
            # Typography belongs to the blog design system, not the source
            # page. Keep layout and data-viz styles, but normalize headings,
            # labels, metadata, and table text to Google Sans and blog weights.
            + ".sr-article h2 { font-family: inherit; font-size: 1.4rem; "
            + "line-height: 1.25; font-weight: 700; letter-spacing: -0.01em; "
            + "margin: 2.25rem 0 0.5rem; color: var(--brand-text); }\n"
            + ".sr-article h3 { font-family: inherit; font-size: 1.15rem; "
            + "line-height: 1.25; font-weight: 700; letter-spacing: -0.01em; "
            + "margin: 1.75rem 0 0.4rem; color: var(--brand-text); }\n"
            + ".sr-article h4 { font-family: inherit; line-height: 1.25; "
            + "font-weight: 700; letter-spacing: -0.01em; color: var(--brand-text); }\n"
            + ".sr-article h2 .n, .sr-article .kicker, .sr-article .meta, "
            + ".sr-article th, .sr-article .tag { font-family: inherit; }\n"
            + ".sr-article h2 .n { font-size: 0.8em; font-weight: 600; }\n"
            + ".sr-article .kicker { font-weight: 600; }\n"
            + ".sr-article .meta, .sr-article .tag { font-weight: 400; }\n"
            + ".sr-article th { font-weight: 600; }\n"
            + ".sr-article .fig-title { font-weight: 600; }\n</style>"
        )
    parts.append(f'<div class="sr-article">\n{ex["body"]}\n</div>')
    if ex["needs_chart"]:
        parts.append('<script src="__ASSETS__/vendor/chart.umd.min.js"></script>')
    for s in ex["scripts"]:
        parts.append(f"<script>\n{s}\n</script>")
    out_body = "\n".join(parts)

    fm_tags = "[" + ", ".join(tags) + "]" if tags else "[]"
    md = (
        "---\n"
        f"title: {title}\n"
        f"slug: {slug}\n"
        f"date: {args.date}\n"
        f"author: {args.author}\n"
        f"description: {desc}\n"
        f"tags: {fm_tags}\n"
        f"draft: {'false' if args.publish else 'true'}\n"
        f"source_url: {args.url}\n"
        "---\n\n"
        f"{out_body}\n"
    )
    out = ROOT / "content" / "posts" / f"{args.date}-{slug}.md"
    out.write_text(md, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes) slug={slug} draft={not args.publish}")
    print("next: python3 build.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
