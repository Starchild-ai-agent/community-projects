#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import unicodedata
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "twitter_articles_5_raw.json"
POSTS = ROOT / "content" / "posts"
ASSETS = ROOT / "assets" / "img"
MARKER = "<!-- imported-from-x -->"
UA = "Mozilla/5.0 (compatible; StarchildBlogImporter/1.0)"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().replace("'", "")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "x-article"


def iso_date(created_at: str) -> str:
    return datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y").date().isoformat()


def clean_line(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def description_from(text: str, fallback: str) -> str:
    s = clean_line(text) or clean_line(fallback)
    if len(s) <= 155:
        return s
    cut = s[:155]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" .,;:") + "…"


def ext_from_url(url: str, default: str = ".jpg") -> str:
    path = urlparse(url).path
    ext = Path(path).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return ext
    return default


def download(url: str, out: Path) -> tuple[bool, str]:
    if out.exists() and out.stat().st_size > 0:
        return True, "cached"
    out.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        out.write_bytes(data)
        return True, f"downloaded {len(data)} bytes"
    except Exception as e:
        return False, str(e)


def md_escape_alt(text: str) -> str:
    return clean_line(text).replace("[", "").replace("]", "")


def block_to_md(block: dict, slug: str, title: str, img_i: int, warnings: list[str]) -> tuple[str, int, int]:
    typ = block.get("type", "unstyled")
    text = block.get("text", "") or ""
    downloaded = 0

    if typ == "image":
        url = block.get("url", "")
        if not url:
            return "", img_i, downloaded
        ext = ext_from_url(url)
        fname = f"image-{img_i}{ext}"
        out = ASSETS / slug / fname
        ok, msg = download(url, out)
        if ok:
            downloaded = 1 if msg.startswith("downloaded") or msg == "cached" else 0
            return f"![{md_escape_alt(title)} image](../../assets/img/{slug}/{fname})", img_i + 1, downloaded
        warnings.append(f"{slug}: image download failed {url}: {msg}")
        return f"![{md_escape_alt(title)} image]({url})", img_i + 1, downloaded

    text = text.rstrip()
    if not text:
        return "", img_i, downloaded
    if typ == "header-one":
        return f"# {text}", img_i, downloaded
    if typ == "header-two":
        return f"## {text}", img_i, downloaded
    if typ == "header-three":
        return f"### {text}", img_i, downloaded
    if typ == "unordered-list-item":
        return f"- {text}", img_i, downloaded
    if typ == "ordered-list-item":
        return f"1. {text}", img_i, downloaded
    if typ == "blockquote":
        return "\n".join(f"> {line}" for line in text.splitlines()), img_i, downloaded
    if typ == "code-block":
        return f"```\n{text}\n```", img_i, downloaded
    return text, img_i, downloaded


def frontmatter_value(value: str) -> str:
    return str(value).replace("\n", " ").strip()


def main() -> int:
    data = json.loads(RAW.read_text(encoding="utf-8"))
    articles = data.get("articles", [])[:5]
    if len(articles) != 5:
        print(f"expected 5 articles, found {len(articles)}", file=sys.stderr)
        return 1

    warnings: list[str] = []
    summaries = []
    for item in articles:
        tweet = item["tweet"]
        article = (item.get("article_detail") or {}).get("article") or tweet.get("article") or {}
        title = clean_line(article.get("title") or (tweet.get("article") or {}).get("title") or tweet.get("text", "Untitled"))
        slug = slugify(title)
        created = article.get("createdAt") or tweet.get("createdAt")
        date = iso_date(created)
        desc = description_from(article.get("preview_text", ""), title)
        tweet_url = tweet.get("url") or f"https://x.com/StarchildOnX/status/{tweet.get('id')}"

        downloaded_count = 0
        og_line = ""
        cover_url = article.get("cover_media_img_url") or (tweet.get("article") or {}).get("cover_media_img_url")
        if cover_url:
            ext = ext_from_url(cover_url)
            cover_name = f"cover{ext}"
            ok, msg = download(cover_url, ASSETS / slug / cover_name)
            if ok:
                downloaded_count += 1
                og_line = f"og_image: /assets/img/{slug}/{cover_name}\n"
            else:
                warnings.append(f"{slug}: cover download failed {cover_url}: {msg}")

        body_parts = []
        if cover_url and og_line:
            body_parts.append(f"![{md_escape_alt(title)} cover](../../assets/img/{slug}/{cover_name})")
        elif cover_url:
            body_parts.append(f"![{md_escape_alt(title)} cover]({cover_url})")

        img_i = 1
        for block in article.get("contents", []):
            md, img_i, dl = block_to_md(block, slug, title, img_i, warnings)
            downloaded_count += dl
            if md:
                body_parts.append(md)

        body_parts.append(f"Originally published on X: {tweet_url}")
        body_parts.append(MARKER)
        body = "\n\n".join(body_parts).strip() + "\n"

        fm = (
            "---\n"
            f"title: {frontmatter_value(title)}\n"
            f"slug: {slug}\n"
            f"date: {date}\n"
            "author: Blog Team\n"
            f"description: {frontmatter_value(desc)}\n"
            "tags: [announcements]\n"
            f"{og_line}"
            "draft: false\n"
            f"source_url: {tweet_url}\n"
            f"x_article_id: {tweet.get('id')}\n"
            "---\n\n"
        )
        out = POSTS / f"{date}-{slug}.md"
        if out.exists() and MARKER not in out.read_text(encoding="utf-8"):
            warnings.append(f"skipped existing manual file: {out.name}")
            continue
        out.write_text(fm + body, encoding="utf-8")
        summaries.append((out.name, title, date, downloaded_count))

    for name, title, date, count in summaries:
        print(f"{date} | {name} | {count} image(s) | {title}")
    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(f"- {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
