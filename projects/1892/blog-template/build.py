#!/usr/bin/env python3
"""Static site generator for a markdown-driven blog.

Reads markdown from content/posts/, renders to HTML using templates/, and
emits a self-contained public/ directory. Absolute URLs in the output are
derived from config.SITE_URL; internal links/asset refs are relative so the
output works under any base path.

CLI modes:
  (no args)  full build; drafts are excluded from public-facing surfaces
             but still rendered to public/drafts/<slug>/index.html.
  --check    parse + validate every post; print a summary; write NOTHING.
             Exits non-zero on any validation error.
  --drafts   like the default build, but drafts also appear on the
             homepage post list, marked "[draft]". Local preview only.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import sys
import tempfile
from datetime import date, datetime, timezone
from email.utils import format_datetime
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import quote as urllib_parse_quote
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import markdown

# Local config (intentionally imported by path so the script is runnable from
# the project root without a package install).
sys.path.insert(0, str(Path(__file__).parent))
# Load config explicitly by file path (a bare `import config` can be shadowed
# by an unrelated package named `config` elsewhere on sys.path). Falls back to
# config.example.py so a fresh fork builds with zero setup.
import importlib.util  # noqa: E402


def _load_config():
    root = Path(__file__).parent
    cfg_path = root / "config.py"
    if not cfg_path.exists():
        cfg_path = root / "config.example.py"
        print(
            "note: config.py not found, using config.example.py defaults. "
            "To customize: cp config.example.py config.py"
        )
    spec = importlib.util.spec_from_file_location("blog_config", cfg_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules["blog_config"] = mod
    return mod


config = _load_config()

ROOT = Path(__file__).parent
CONTENT_DIR = ROOT / "content" / "posts"
TEMPLATES_DIR = ROOT / "templates"
ASSETS_DIR = ROOT / "assets"
PUBLIC_DIR = ROOT / "public"
OG_DIR = PUBLIC_DIR / "og"

sys.path.insert(0, str(ROOT / "scripts"))
import og_image  # noqa: E402

# Words per minute used for the static "reading_minutes" estimate.
WORDS_PER_MINUTE = 220


def _utm_url(
    base: str,
    *,
    medium: str,
    content: str | None = None,
    campaign: str | None = None,
) -> str:
    """Append standard blog UTM params to an outbound marketing URL.

    Preserves any existing query string. Does not rewrite fragments.
    Use only on conversion/marketing destinations (nav, footer, CTAs).
    Do not apply to internal blog links, assets, RSS, or JSON-LD.
    """
    parts = urlsplit(base)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q["utm_source"] = config.UTM_SOURCE
    q["utm_medium"] = medium
    camp = campaign if campaign is not None else config.UTM_CAMPAIGN
    if camp:
        q["utm_campaign"] = camp
    if content:
        q["utm_content"] = content
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment)
    )

# ---------------------------------------------------------------------------
# Frontmatter (hand-rolled; ~30 lines)
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)

# Strip HTML tags from rendered markdown to get plain text. Not a full
# sanitizer; we just need a readable word count and a no-markup body for
# the posts-full.json API.
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_BODY_TEXT_BLOCK_RE = re.compile(
    r"<pre.*?</pre>|<code.*?</code>", re.DOTALL | re.IGNORECASE
)


def _strip_html(html: str) -> str:
    # Drop fenced code blocks entirely -- they inflate word counts with code
    # identifiers and aren't natural reading material.
    text = _BODY_TEXT_BLOCK_RE.sub(" ", html)
    text = _TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def _word_count(text: str) -> int:
    return len([w for w in text.split(" ") if w])


def _json_dumps(obj) -> str:
    """Stable, no HTML-escaping JSON for inline scripts and API output."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def parse_post(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    if not m:
        raise SystemExit(f"[{path.name}] missing or malformed frontmatter")
    fm_block, body = m.group(1), m.group(2)
    meta: dict = {}
    list_key: str | None = None
    for raw in fm_block.splitlines():
        if not raw.strip():
            continue
        if raw.lstrip().startswith("- ") and list_key:
            meta[list_key].append(raw.lstrip()[2:].strip())
            continue
        if ":" not in raw:
            raise SystemExit(f"[{path.name}] bad frontmatter line: {raw!r}")
        key, _, value = raw.partition(":")
        key = key.strip()
        value = value.strip()
        if value == "":
            meta[key] = []
            list_key = key
            continue
        list_key = None
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            meta[key] = [t.strip().strip("'\"") for t in inner.split(",") if t.strip()] if inner else []
        elif value in ("true", "false"):
            meta[key] = (value == "true")
        else:
            meta[key] = value.strip("'\"")

    for required in ("title", "date", "description"):
        if required not in meta:
            raise SystemExit(f"[{path.name}] missing required frontmatter: {required}")
    desc = meta["description"]
    if len(desc) > 160:
        raise SystemExit(f"[{path.name}] description >160 chars ({len(desc)})")
    if not isinstance(meta.get("tags", []), list):
        raise SystemExit(f"[{path.name}] tags must be a list")
    if "slug" not in meta:
        meta["slug"] = path.stem.split("-", 3)[-1] if path.stem[:10].count("-") >= 2 else path.stem
    if "author" not in meta:
        meta["author"] = config.DEFAULT_AUTHOR
    if "draft" not in meta:
        meta["draft"] = False
    meta["_body_md"] = body
    meta["_path"] = path
    return meta


def load_posts() -> list[dict]:
    posts = []
    for p in sorted(CONTENT_DIR.glob("*.md")):
        posts.append(parse_post(p))
    # Newest first; sort by date string (ISO YYYY-MM-DD sorts correctly).
    posts.sort(key=lambda x: x["date"], reverse=True)
    return posts


def _check_slug_uniqueness(posts: list[dict]) -> None:
    seen: dict[str, str] = {}
    for p in posts:
        slug = p["slug"]
        if slug in seen:
            raise SystemExit(
                f"duplicate slug {slug!r} in {p['_path'].name} "
                f"(also in {seen[slug]})"
            )
        seen[slug] = p["_path"].name


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

_md = markdown.Markdown(extensions=["fenced_code", "tables"])


def render_markdown(body_md: str) -> str:
    _md.reset()
    return _md.convert(body_md)


# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------

def abs_url(path: str) -> str:
    """Absolute URL for a path on the site (leading slash, no host)."""
    if not path.startswith("/"):
        path = "/" + path
    return config.SITE_URL.rstrip("/") + path


def site_icon_url() -> str:
    return abs_url(config.ICON_PATH)


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

def _tpl(name: str) -> Template:
    return Template((TEMPLATES_DIR / name).read_text(encoding="utf-8"))


def rel_from(current_page_dir: str, target: str) -> str:
    """Relative path from current page directory to target asset path.

    current_page_dir is '' for the site root, 'posts/<slug>/' for a post,
    'tags/<tag>/' for a tag page. target is a path relative to the site root
    (e.g. 'assets/style.css', 'posts/<slug>/index.html', 'index.html').
    """
    if not current_page_dir:
        return target
    depth = current_page_dir.rstrip("/").count("/") + 1
    return "../" * depth + target


_ICON_CACHE: dict[str, str] = {}


def _icon(name: str) -> str:
    """Read assets/icons/{name}.svg and return the SVG markup with
    aria-hidden="true" and class="icon" injected on the <svg> tag.
    Cached on first read."""
    cached = _ICON_CACHE.get(name)
    if cached is not None:
        return cached
    path = ASSETS_DIR / "icons" / f"{name}.svg"
    svg = path.read_text(encoding="utf-8")
    # Inject attributes on the existing <svg ...> tag.
    if 'aria-hidden' not in svg:
        svg = svg.replace("<svg ", '<svg aria-hidden="true" class="icon" ', 1)
    _ICON_CACHE[name] = svg
    return svg


def _nav_html(current_page_dir: str) -> str:
    home = rel_from(current_page_dir, "index.html")
    wordmark = rel_from(current_page_dir, "assets/wordmark.svg")
    cta_href = _utm_url(config.CTA_URL, medium="nav")
    return (
        f'<nav class="topnav" aria-label="Site">'
        f'<div class="wrap">'
        f'<a class="brand" href="{escape(home)}">'
        f'<img src="{escape(wordmark)}" alt="{escape(config.SITE_NAME)}">'
        f'</a>'
        f'<div class="nav-actions">'
        f'<a class="cta" href="{escape(cta_href)}">{escape(config.CTA_TEXT)}</a>'
        f'</div>'
        f'</div>'
        f'</nav>'
    )


def _action_row(post: dict, current_page_dir: str, compact: bool = False) -> str:
    """Article action row: back / share / copy / post on X.

    compact=True omits the left-side back link and uses the .compact variant
    (border-top) so two rows visually frame the article.
    """
    home = rel_from(current_page_dir, "index.html")
    canonical = abs_url(f"/posts/{post['slug']}/")
    title = post["title"]
    tweet_text = urllib_parse_quote(title)
    tweet_url = urllib_parse_quote(canonical)
    tweet_href = f"https://twitter.com/intent/tweet?text={tweet_text}&url={tweet_url}"
    classes = "post-actions compact" if compact else "post-actions"

    back = (
        f'<a class="back" href="{escape(home)}">'
        f'{_icon("arrow_back")}<span>All posts</span></a>'
    )

    right = (
        f'<button type="button" class="act" data-copy>'
        f'{_icon("content_copy")}<span></span></button>'
        f'<a class="act" href="{escape(tweet_href)}" target="_blank" rel="noopener">'
        f'{_icon("x_logo")}<span>Post on X</span></a>'
    )

    if compact:
        return f'<nav class="{classes}" aria-label="Article actions">{right}</nav>'
    return f'<nav class="{classes}" aria-label="Article actions">{back}<div class="acts-right">{right}</div></nav>'


def _cta_block(slug: str) -> str:
    # Per-article attribution: utm_content=<slug> so product analytics can
    # rank which posts drive Create-your-agent clicks.
    href = _utm_url(config.CTA_URL, medium="article_cta", content=slug)
    return (
        f'<aside class="agent-cta">'
        f'<div class="agent-cta-body">'
        f'<h2>Put an agent to work on this</h2>'
        f'<p>Starchild agents read, build, and trade for you.</p>'
        f'</div>'
        f'<a class="cta" href="{escape(href)}">{escape(config.CTA_TEXT)}</a>'
        f'</aside>'
    )


def _prevnext_html(posts_sorted: list[dict], current: dict, current_page_dir: str) -> str:
    """Emit prev/next links for the current post. posts_sorted is newest-first.

    prev = next-newer (i.e. the post one slot earlier in the list).
    next = next-older (i.e. the post one slot later in the list).
    Omit the side that is missing.
    """
    try:
        i = posts_sorted.index(current)
    except ValueError:
        return ""
    newer = posts_sorted[i - 1] if i - 1 >= 0 else None
    older = posts_sorted[i + 1] if i + 1 < len(posts_sorted) else None
    parts = []
    if newer is not None:
        href = rel_from(current_page_dir, f"posts/{newer['slug']}/index.html")
        parts.append(
            f'<a class="prev" href="{escape(href)}">'
            f'&larr; {escape(newer["title"])}</a>'
        )
    if older is not None:
        href = rel_from(current_page_dir, f"posts/{older['slug']}/index.html")
        parts.append(
            f'<a class="next" href="{escape(href)}">'
            f'{escape(older["title"])} &rarr;</a>'
        )
    if not parts:
        return ""
    return f'<nav class="prevnext" aria-label="More posts">{"".join(parts)}</nav>'


def nav_js_tag(current_page_dir: str) -> str:
    """Emit a deferred <script> for nav.js, with a page-relative src."""
    src = rel_from(current_page_dir, "assets/nav.js")
    return f'<script src="{escape(src)}" defer></script>'


def _rss_link_tag(current_page_dir: str) -> str:
    href = rel_from(current_page_dir, "feed.xml")
    return (
        f'<link rel="alternate" type="application/rss+xml" '
        f'title="{escape(config.SITE_NAME)}" href="{escape(href)}">'
    )


def _common(current_page_dir: str, *, title: str, description: str,
            canonical_path: str, og_image_path: str | None,
            og_type: str | None) -> dict:
    canonical = abs_url(canonical_path)
    style_url = rel_from(current_page_dir, "assets/style.css")
    wordmark_url = rel_from(current_page_dir, config.WORDMARK_PATH.lstrip("/"))
    icon_url = rel_from(current_page_dir, config.ICON_PATH.lstrip("/").rsplit(".", 1)[0] + ".svg")
    icon_png_url = rel_from(current_page_dir, config.ICON_PATH.lstrip("/"))
    home_url = rel_from(current_page_dir, "index.html") or "index.html"

    og_image_tag = ""
    twitter_image_tag = ""
    if og_image_path:
        og_abs = abs_url(og_image_path)
        og_image_tag = f'<meta property="og:image" content="{escape(og_abs)}">'
        twitter_image_tag = f'<meta name="twitter:image" content="{escape(og_abs)}">'
    og_type_tag = f'<meta property="og:type" content="{escape(og_type)}">' if og_type else ""

    return dict(
        title=title,
        description=description,
        canonical=canonical,
        icon_url=icon_url,
        icon_png_url=icon_png_url,
        style_url=style_url,
        wordmark_url=wordmark_url,
        home_url=home_url,
        og_title=title,
        og_description=description,
        og_image_tag=og_image_tag,
        og_type_tag=og_type_tag,
        twitter_image_tag=twitter_image_tag,
        site_name=config.SITE_NAME,
        site_tagline=config.SITE_TAGLINE,
        org_url=_utm_url(config.ORG_URL, medium="footer"),
        cta_text=config.CTA_TEXT,
        rss_link_tag=_rss_link_tag(current_page_dir),
        nav_html=_nav_html(current_page_dir),
    )


def _tag_pills_html(tags: list[str], current_page_dir: str) -> str:
    if not tags:
        return ""
    items = []
    for t in tags:
        href = rel_from(current_page_dir, f"tags/{t}/index.html")
        items.append(f'<li><a href="{escape(href)}">#{escape(t)}</a></li>')
    return f'<ul class="tags">{"".join(items)}</ul>'


def _card_image_html(post: dict, current_page_dir: str, class_name: str = "card-image") -> str:
    """Return a 5:2 card image pulled from post og_image when available."""
    img = (post.get("og_image") or "").strip()
    if not img or img.startswith("http://") or img.startswith("https://"):
        return ""
    img_path = img.lstrip("/")
    src = rel_from(current_page_dir, img_path)
    alt = f"{post['title']} graphic"
    href = rel_from(current_page_dir, f"posts/{post['slug']}/index.html")
    return (
        f'<a class="{escape(class_name)}" href="{escape(href)}" '
        f'aria-label="Read {escape(post["title"])}">'
        f'<img src="{escape(src)}" alt="{escape(alt)}" loading="lazy">'
        f'</a>'
    )


def _post_list_html(posts: list[dict], current_page_dir: str) -> str:
    items = []
    for p in posts:
        href = rel_from(current_page_dir, f"posts/{p['slug']}/index.html")
        date_disp = p["date"]
        draft_badge = (
            ' <span class="draft-badge">[draft]</span>' if p.get("draft") else ""
        )
        image_html = _card_image_html(p, current_page_dir)
        items.append(
            f'<li class="post-card">'
            f'{image_html}'
            f'<div class="post-card-body">'
            f'<h2><a href="{escape(href)}">{escape(p["title"])}</a>{draft_badge}</h2>'
            f'<p class="meta"><time datetime="{escape(p["date"])}">{escape(date_disp)}</time></p>'
            f'<p>{escape(p["description"])}</p>'
            f'{_tag_pills_html(p.get("tags", []), current_page_dir)}'
            f'</div>'
            f'</li>'
        )
    return f'<ul class="post-list">{"".join(items)}</ul>'


def render_home(posts: list[dict], tags: dict[str, list[dict]]) -> str:
    default_og = _ensure_og_image("default", config.SITE_NAME, config.SITE_TAGLINE)
    base = _common(
        "",
        title=config.SITE_NAME + " -- " + config.SITE_TAGLINE,
        description=config.SITE_DESCRIPTION,
        canonical_path="/",
        og_image_path=default_og,
        og_type="website",
    )

    if posts:
        featured = posts[0]
        others = posts[1:]
        featured_url = rel_from("", f"posts/{featured['slug']}/index.html")
        draft_badge = (
            ' <span class="draft-badge">[draft]</span>' if featured.get("draft") else ""
        )
        featured_image = _card_image_html(featured, "", "featured-image")
        featured_block = (
            f'<section class="featured" aria-label="Latest post">'
            f'{featured_image}'
            f'<div class="featured-body">'
            f'<p class="eyebrow">Latest</p>'
            f'<h2><a href="{escape(featured_url)}">{escape(featured["title"])}</a>{draft_badge}</h2>'
            f'<p>{escape(featured["description"])}</p>'
            f'<p class="meta"><time datetime="{escape(featured["date"])}">{escape(featured["date"])}</time></p>'
            f'{_tag_pills_html(featured.get("tags", []), "")}'
            f'</div>'
            f'</section>'
        )
        post_list_html = _post_list_html(others, "")
    else:
        featured_block = '<p>No posts yet.</p>'
        post_list_html = ""

    # Tag section hidden from the homepage for now; tag pages/metadata remain.
    tag_block = ""

    org_jsonld = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Starchild",
        "url": config.ORG_URL,  # bare org URL for schema; never UTM-tag JSON-LD
        "logo": site_icon_url(),
    }
    blog_jsonld = {
        "@context": "https://schema.org",
        "@type": "Blog",
        "name": config.SITE_NAME,
        "description": config.SITE_DESCRIPTION,
        "url": abs_url("/"),
    }
    jsonld = (
        '<script type="application/ld+json">'
        + _json_dumps(blog_jsonld)
        + '</script>\n<script type="application/ld+json">'
        + _json_dumps(org_jsonld)
        + '</script>'
    )

    home_tpl = _tpl("home.html")
    body = home_tpl.substitute(
        site_name=config.SITE_NAME,
        site_tagline=config.SITE_TAGLINE,
        featured_block=featured_block,
        post_list_html=post_list_html,
        tag_block=tag_block,
        jsonld=jsonld,
    )
    base_tpl = _tpl("base.html")
    return base_tpl.substitute(**base, body=body, extra_head="", extra_body=nav_js_tag(""))


def render_post(post: dict, published: list[dict] | None = None) -> str:
    body_html = render_markdown(post["_body_md"]).replace("__ASSETS__", "../../assets")
    canonical_path = f"/posts/{post['slug']}/"
    og_image_path = _resolve_og_image(post)
    base = _common(
        f"posts/{post['slug']}/",
        title=f"{post['title']} | {config.SITE_NAME}",
        description=post["description"],
        canonical_path=canonical_path,
        og_image_path=og_image_path,
        og_type="article",
    )
    updated_html = ""
    if post.get("updated"):
        updated_html = (
            f' (updated <time datetime="{escape(post["updated"])}">'
            f'{escape(post["updated"])}</time>)'
        )
    author_html = ""  # Author byline hidden in UI; kept in JSON-LD/meta.

    article_jsonld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post["title"],
        "description": post["description"],
        "datePublished": post["date"],
        "dateModified": post.get("updated", post["date"]),
        "image": abs_url(og_image_path),
        "author": {"@type": "Organization", "name": post["author"]},
        "publisher": {
            "@type": "Organization",
            "name": "Starchild",
            "logo": {"@type": "ImageObject", "url": site_icon_url()},
        },
        "mainEntityOfPage": abs_url(canonical_path),
    }
    jsonld = (
        '<script type="application/ld+json">'
        + _json_dumps(article_jsonld)
        + '</script>'
    )

    # article:published_time is a nice-to-have extension; emit it as extra head.
    extra_head = (
        f'<meta property="article:published_time" content="{escape(post["date"])}">'
    )
    if post.get("updated"):
        extra_head += f'<meta property="article:modified_time" content="{escape(post["updated"])}">'
    for t in post.get("tags", []):
        extra_head += f'<meta property="article:tag" content="{escape(t)}">'

    post_tpl = _tpl("post.html")
    page_dir = f"posts/{post['slug']}/"
    action_row_top = _action_row(post, page_dir, compact=False)
    action_row_bottom = _action_row(post, page_dir, compact=True)
    cta_block = _cta_block(post["slug"])
    if published is not None:
        prevnext_html = _prevnext_html(published, post, page_dir)
    else:
        prevnext_html = ""
    hero_img = (post.get("hero_image") or "").strip()
    if hero_img:
        hero_src = rel_from(page_dir, hero_img)
        hero_html = (
            f'<div class="post-hero">'
            f'<img src="{escape(hero_src)}" alt="{escape(post["title"])}" loading="eager">'
            f'</div>'
        )
    else:
        hero_html = ""
    body = post_tpl.substitute(
        title=post["title"],
        date_iso=post["date"],
        date_display=post["date"],
        updated_html=updated_html,
        author_html=author_html,
        hero_html=hero_html,
        body_html=body_html,
        jsonld=jsonld,
        action_row_top=action_row_top,
        action_row_bottom=action_row_bottom,
        cta_block=cta_block,
        prevnext_html=prevnext_html,
    )
    base_tpl = _tpl("base.html")
    return base_tpl.substitute(**base, body=body, extra_head=extra_head, extra_body=nav_js_tag(page_dir))


def render_tag(tag: str, posts: list[dict]) -> str:
    canonical_path = f"/tags/{tag}/"
    base = _common(
        f"tags/{tag}/",
        title=f"#{tag} | {config.SITE_NAME}",
        description=f"Posts tagged #{tag} on {config.SITE_NAME}.",
        canonical_path=canonical_path,
        og_image_path=config.ICON_PATH,
        og_type="website",
    )
    post_list_html = _post_list_html(posts, f"tags/{tag}/")
    tag_tpl = _tpl("tag.html")
    body = tag_tpl.substitute(
        tag=tag,
        post_count=len(posts),
        post_list_html=post_list_html,
    )
    base_tpl = _tpl("base.html")
    return base_tpl.substitute(**base, body=body, extra_head="", extra_body=nav_js_tag(f"tags/{tag}/"))


def render_draft(post: dict) -> str:
    """Render a draft to its standalone preview page (noindex).

    Reuses the public post layout so the local preview is identical to the
    eventual published article. The only SEO-affecting change is the
    noindex meta tag in extra_head.
    """
    body_html = render_markdown(post["_body_md"]).replace("__ASSETS__", "../assets")
    canonical_path = f"/drafts/{post['slug']}/"
    base = _common(
        f"drafts/{post['slug']}/",
        title=f"{post['title']} [draft] | {config.SITE_NAME}",
        description=post["description"],
        canonical_path=canonical_path,
        og_image_path=_resolve_og_image(post),
        og_type=None,
    )
    updated_html = ""
    if post.get("updated"):
        updated_html = (
            f' (updated <time datetime="{escape(post["updated"])}">'
            f'{escape(post["updated"])}</time>)'
        )
    author_html = ""  # Author byline hidden in UI; kept in JSON-LD/meta.

    extra_head = '<meta name="robots" content="noindex">'
    extra_head += (
        f'<meta property="article:published_time" content="{escape(post["date"])}">'
    )
    if post.get("updated"):
        extra_head += f'<meta property="article:modified_time" content="{escape(post["updated"])}">'
    for t in post.get("tags", []):
        extra_head += f'<meta property="article:tag" content="{escape(t)}">'

    post_tpl = _tpl("post.html")
    page_dir = f"drafts/{post['slug']}/"
    action_row_top = _action_row(post, page_dir, compact=False)
    action_row_bottom = _action_row(post, page_dir, compact=True)
    cta_block = _cta_block(post["slug"])
    prevnext_html = ""
    hero_img = (post.get("hero_image") or "").strip()
    if hero_img:
        hero_src = rel_from(page_dir, hero_img)
        hero_html = (
            f'<div class="post-hero">'
            f'<img src="{escape(hero_src)}" alt="{escape(post["title"])}" loading="eager">'
            f'</div>'
        )
    else:
        hero_html = ""
    body = post_tpl.substitute(
        title=post["title"],
        date_iso=post["date"],
        date_display=post["date"],
        updated_html=updated_html,
        author_html=author_html,
        hero_html=hero_html,
        body_html=body_html,
        jsonld="",
        action_row_top=action_row_top,
        action_row_bottom=action_row_bottom,
        cta_block=cta_block,
        prevnext_html=prevnext_html,
    )
    base_tpl = _tpl("base.html")
    rendered = base_tpl.substitute(**base, body=body, extra_head=extra_head, extra_body=nav_js_tag(page_dir))
    # Drafts are served BOTH under the full site root (public/) and from a
    # standalone drafts preview whose root is public/drafts/. Assets are
    # mirrored to public/drafts/assets/, so shifting every root-climbing
    # reference one level up ('../../x' -> '../x') keeps pages working in
    # both contexts.
    return rendered.replace("../../", "../")


def render_drafts_index(drafts: list[dict]) -> str:
    """Standalone index of all drafts at public/drafts/index.html.

    Self-contained (inline CSS, no template deps) so it renders correctly
    whether served from the site root or as the root of a drafts-only
    preview. noindex; /drafts/ is already disallowed in robots.txt.
    """
    rows = []
    for p in sorted(drafts, key=lambda x: x["date"], reverse=True):
        rows.append(
            f'<li><a href="{escape(p["slug"])}/">{escape(p["title"])}</a>'
            f'<span class="d">{escape(p["date"])}</span>'
            f'<p>{escape(p["description"])}</p></li>'
        )
    items = "\n".join(rows) if rows else "<li><p>No drafts right now.</p></li>"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Drafts | {escape(config.SITE_NAME)}</title>
<style>
body{{font-family:'Google Sans',Inter,system-ui,sans-serif;color:#111;background:#fff;max-width:720px;margin:0 auto;padding:48px 20px}}
h1{{font-size:22px}} h1 span{{color:#F84600}}
ul{{list-style:none;padding:0}}
li{{border:1px solid #eee;border-radius:10px;padding:16px 18px;margin:12px 0}}
a{{color:#F84600;font-weight:600;text-decoration:none;font-size:16px}}
a:hover{{text-decoration:underline}}
.d{{color:#888;font-size:12.5px;margin-left:10px}}
p{{color:#555;font-size:14px;margin:6px 0 0}}
</style>
</head>
<body>
<h1><span>Drafts</span> — {escape(config.SITE_NAME)}</h1>
<p>Internal review pages. Not published, not indexed, not in the feed.</p>
<ul>
{items}
</ul>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Machine outputs: feed, sitemap, robots, JSON APIs, redirects
# ---------------------------------------------------------------------------

def _rfc822(dt_str: str) -> str:
    """Convert an ISO date or datetime string to RFC 822 for RSS pubDate."""
    if "T" in dt_str:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    else:
        dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return format_datetime(dt)


def _reading_minutes(html: str) -> int:
    words = _word_count(_strip_html(html))
    return max(1, math.ceil(words / WORDS_PER_MINUTE))


def _post_record(post: dict) -> dict:
    body_html = post.get("_rendered_html") or render_markdown(post["_body_md"])
    if not post.get("_rendered_html"):
        post["_rendered_html"] = body_html
    body_html = body_html.replace("__ASSETS__", abs_url("/assets"))
    url = abs_url(f"/posts/{post['slug']}/")
    return {
        "slug": post["slug"],
        "title": post["title"],
        "date": post["date"],
        "updated": post.get("updated", ""),
        "description": post["description"],
        "tags": list(post.get("tags", [])),
        "url": url,
        "word_count": _word_count(_strip_html(body_html)),
        "reading_minutes": _reading_minutes(body_html),
    }


def render_feed(posts: list[dict]) -> str:
    items = []
    for p in posts:
        body_html = p.get("_rendered_html") or render_markdown(p["_body_md"])
        if not p.get("_rendered_html"):
            p["_rendered_html"] = body_html
        body_html = body_html.replace("__ASSETS__", abs_url("/assets"))
        url = abs_url(f"/posts/{p['slug']}/")
        pub = p.get("updated") or p["date"]
        items.append(
            "  <item>\n"
            f"    <title>{escape(p['title'])}</title>\n"
            f"    <link>{escape(url)}</link>\n"
            f"    <guid isPermaLink=\"true\">{escape(url)}</guid>\n"
            f"    <pubDate>{escape(_rfc822(pub))}</pubDate>\n"
            f"    <description>{escape(p['description'])}</description>\n"
            f"    <content:encoded><![CDATA[{body_html}]]></content:encoded>\n"
            "  </item>"
        )
    last = posts[0] if posts else None
    last_build = _rfc822(
        (last.get("updated") or last["date"]) if last else
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/" '
        'xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        f"    <title>{escape(config.SITE_NAME)}</title>\n"
        f"    <link>{escape(abs_url('/'))}</link>\n"
        f"    <description>{escape(config.SITE_DESCRIPTION)}</description>\n"
        f"    <atom:link href=\"{escape(abs_url('/feed.xml'))}\" "
        f"rel=\"self\" type=\"application/rss+xml\"/>\n"
        f"    <lastBuildDate>{escape(last_build)}</lastBuildDate>\n"
        + "\n".join(items) + "\n"
        "  </channel>\n"
        "</rss>\n"
    )


def render_sitemap(posts: list[dict], tags: dict[str, list[dict]]) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = [
        f"  <url>\n    <loc>{escape(abs_url('/'))}</loc>\n    <lastmod>{today}</lastmod>\n  </url>"
    ]
    for p in posts:
        lastmod = p.get("updated") or p["date"]
        post_url = abs_url(f"/posts/{p['slug']}/")
        urls.append(
            f"  <url>\n"
            f"    <loc>{escape(post_url)}</loc>\n"
            f"    <lastmod>{escape(lastmod)}</lastmod>\n"
            f"  </url>"
        )
    for t in sorted(tags.keys()):
        dated = [p.get("updated") or p["date"] for p in tags[t]]
        lastmod = max(dated) if dated else today
        urls.append(
            f"  <url>\n"
            f"    <loc>{escape(abs_url(f'/tags/{t}/'))}</loc>\n"
            f"    <lastmod>{escape(lastmod)}</lastmod>\n"
            f"  </url>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls) + "\n"
        "</urlset>\n"
    )


def render_robots() -> str:
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /drafts/\n"
        f"Sitemap: {abs_url('/sitemap.xml')}\n"
    )


def render_posts_json(posts: list[dict], full: bool) -> str:
    records = [_post_record(p) for p in posts]
    if full:
        for rec, p in zip(records, posts):
            body_html = p.get("_rendered_html") or render_markdown(p["_body_md"])
            if not p.get("_rendered_html"):
                p["_rendered_html"] = body_html
            rec["body_text"] = _strip_html(body_html)
    payload = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(records),
        "posts": records,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def render_redirects(posts: list[dict], tags: dict[str, list[dict]]) -> str:
    paths = ["/"]
    for p in posts:
        paths.append(f"/posts/{p['slug']}/")
    for t in sorted(tags.keys()):
        paths.append(f"/tags/{t}/")
    payload = {"base_url": config.SITE_URL, "paths": paths}
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


# ---------------------------------------------------------------------------
# Build orchestration
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_tag_index(posts: list[dict]) -> dict[str, list[dict]]:
    tags: dict[str, list[dict]] = {}
    for p in posts:
        for t in p.get("tags", []):
            tags.setdefault(t, []).append(p)
    return tags


def _clear_public() -> None:
    # Stash any existing OG images so we can put them back after wiping
    # public/ — the OG step is idempotent and skips work if the file
    # already exists on disk.
    og_stash: Path | None = None
    if OG_DIR.exists():
        og_stash = Path(tempfile.mkdtemp(prefix="og_stash_"))
        shutil.copytree(OG_DIR, og_stash / "og")
    if PUBLIC_DIR.exists():
        shutil.rmtree(PUBLIC_DIR)
    PUBLIC_DIR.mkdir(parents=True)
    # Preserve asset directory if it exists in source.
    if ASSETS_DIR.exists():
        shutil.copytree(ASSETS_DIR, PUBLIC_DIR / "assets")
    if og_stash is not None:
        shutil.copytree(og_stash / "og", OG_DIR)
        shutil.rmtree(og_stash)


def _ensure_og_image(slug: str, title: str, date: str) -> str:
    """Generate ``public/og/<slug>.png`` if missing. Returns site-root path."""
    out = OG_DIR / f"{slug}.png"
    if not out.exists():
        og_image.generate_og(title, date, str(out))
    return f"/og/{slug}.png"


def _resolve_og_image(post: dict) -> str:
    """Return the site-root path to use for this post's OG image.

    If frontmatter sets ``og_image``, that value is used verbatim (legacy
    behavior). Otherwise a per-post card is generated under public/og/ on
    demand; existing files are not regenerated.
    """
    explicit = post.get("og_image")
    if explicit:
        return explicit
    date_line = post.get("date", "")
    return _ensure_og_image(post["slug"], post["title"], date_line)


def _check_only(posts: list[dict]) -> int:
    errors = 0
    tags = _build_tag_index(posts)
    for p in posts:
        try:
            _ = render_markdown(p["_body_md"])
        except Exception as e:
            print(f"ERROR  {p['_path'].name}: render failed: {e}")
            errors += 1
    drafts = [p for p in posts if p.get("draft")]
    published = [p for p in posts if not p.get("draft")]
    print(
        f"checked {len(posts)} posts "
        f"({len(published)} published, {len(drafts)} drafts), "
        f"{len(tags)} tag(s), "
        f"{'OK' if errors == 0 else f'{errors} error(s)'}"
    )
    return 1 if errors else 0


def main(argv: list[str]) -> int:
    check = "--check" in argv
    drafts_mode = "--drafts" in argv
    posts = load_posts()
    _check_slug_uniqueness(posts)
    if check:
        return _check_only(posts)

    published = [p for p in posts if not p.get("draft")]
    drafts = [p for p in posts if p.get("draft")]

    if drafts_mode:
        home_posts = posts
    else:
        home_posts = published

    _clear_public()

    # Homepage
    home_tags = _build_tag_index(home_posts)
    _write(PUBLIC_DIR / "index.html", render_home(home_posts, home_tags))

    # Published post pages
    published_tags = _build_tag_index(published)
    for p in published:
        _write(
            PUBLIC_DIR / "posts" / p["slug"] / "index.html",
            render_post(p, published=published),
        )

    # In drafts mode, also render drafts to posts/<slug>/ with the normal
    # post template so homepage and tag page links resolve with correct
    # canonicals and prev/next navigation.
    if drafts_mode:
        for p in drafts:
            _write(
                PUBLIC_DIR / "posts" / p["slug"] / "index.html",
                render_post(p, published=home_posts),
            )

    # Tag pages (use published only; with --drafts, include drafts too)
    tag_source = home_posts
    tag_index = _build_tag_index(tag_source)
    for t, plist in tag_index.items():
        _write(
            PUBLIC_DIR / "tags" / t / "index.html",
            render_tag(t, plist),
        )

    # Drafts: standalone preview pages only.
    for p in drafts:
        _write(
            PUBLIC_DIR / "drafts" / p["slug"] / "index.html",
            render_draft(p),
        )
    # Drafts index + mirrored assets so public/drafts/ works as the root of
    # a standalone drafts preview (draft pages reference ../assets/).
    _write(PUBLIC_DIR / "drafts" / "index.html", render_drafts_index(drafts))
    drafts_assets = PUBLIC_DIR / "drafts" / "assets"
    if drafts_assets.exists():
        shutil.rmtree(drafts_assets)
    shutil.copytree(ASSETS_DIR, drafts_assets)

    # Machine outputs -- always use published-only set.
    _write(PUBLIC_DIR / "feed.xml", render_feed(published))
    _write(PUBLIC_DIR / "sitemap.xml", render_sitemap(published, published_tags))
    _write(PUBLIC_DIR / "robots.txt", render_robots())
    _write(PUBLIC_DIR / "api" / "posts.json", render_posts_json(published, full=False))
    _write(PUBLIC_DIR / "api" / "posts-full.json", render_posts_json(published, full=True))
    _write(PUBLIC_DIR / "redirects.json", render_redirects(published, published_tags))

    print(
        f"built {len(published)} post(s), {len(drafts)} draft(s), "
        f"{len(tag_index)} tag(s) "
        f"{'(drafts visible on homepage)' if drafts_mode else ''}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
