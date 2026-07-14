---
name: agent-blog
description: End-to-end blog management for AI agents. Write, import, build, preview, and publish articles using the blog template. Covers draft workflow, article import, SEO, OG images, and deployment.
author: Starchild
tags: ["blog", "content", "publishing", "seo", "static-site"]
user-invocable: true
---

# Agent Blog Skill

Manage a blog built on the blog template. Full lifecycle: write or import
drafts, format articles, set titles and hero images, add SEO structures,
build, preview, and publish.

## Project layout

```
config.py                  site constants (SITE_URL, SITE_NAME, CTA, UTM, OG colors)
build.py                   generator; python3 build.py [--check|--drafts]
scripts/import_article.py  import any HTML article as a draft
scripts/import_x_articles.py  import X articles as drafts
scripts/og_image.py        auto-generate OG cards from post titles
templates/                 base.html, home.html, post.html, tag.html
assets/                    style.css, fonts, icons, vendor/chart.umd.min.js
assets/images/             hero images live here
content/posts/             YYYY-MM-DD-<slug>.md source files
public/                    build output (gitignored)
```

## Config

`config.py` is the single source of truth. If it does not exist, the build
falls back to `config.example.py` defaults (with a printed note), so a fresh
fork builds with zero setup. To customize: copy `config.example.py` to
`config.py` and edit the values.

Key fields: `SITE_URL`, `SITE_NAME`, `SITE_TAGLINE`, `CTA_URL`, `CTA_TEXT`,
`OG_*` colors, `UTM_SOURCE`.

## Writing a post

Create `content/posts/YYYY-MM-DD-<slug>.md`:

```yaml
---
title: "Post Title"
slug: post-title
date: 2026-01-15
author: Author Name
description: "Short SEO summary."
tags: [tag1, tag2]
draft: true
og_image: /assets/images/hero.png
---
```

Then `python3 build.py`. Drafts render to `public/drafts/<slug>/` and are
excluded from homepage, RSS, sitemap. Set `draft: false` to publish.

### Frontmatter fields

| Field | Required | Notes |
|-------|----------|-------|
| title | yes | Wrap in quotes if it contains `:` or `#` |
| slug | no | Defaults to filename slug |
| date | no | Defaults to filename date |
| author | no | Defaults to `config.DEFAULT_AUTHOR` |
| description | no | Falls back to first 160 chars of body |
| tags | no | YAML list `[a, b]` |
| draft | no | `true` = excluded from public surfaces |
| og_image | no | Custom OG image path; auto-generated if omitted |
| source_url | no | Original URL if imported |

### Body

Standard markdown after the `---`. Supports headings, bold, italic, links,
images, code blocks, blockquotes, lists, tables, horizontal rules.

For raw HTML articles (imported), the body can contain inline `<style>`
and `<script>` blocks. The importer scopes CSS under `.sr-article`.

## Importing articles

### From any HTML URL

```bash
python3 scripts/import_article.py "URL" \
    --date YYYY-MM-DD --slug S --title "T" \
    --author "Author" --tags a,b --description "..."
```

The importer fetches the page, extracts body + styles + scripts, scopes
CSS under `.sr-article`, drops the original `<h1>`, rewrites Chart.js CDN
to vendored copy, and writes a draft markdown file.

### From X articles

```bash
python3 scripts/import_x_articles.py
```

Reads `twitter_articles_5_raw.json` (or similar export), downloads cover
images, and writes formatted markdown posts.

## Building

```bash
python3 build.py --check    # validate only, write nothing
python3 build.py            # full build (drafts excluded from public surfaces)
python3 build.py --drafts   # full build (drafts visible on homepage, marked [draft])
```

Output goes to `public/`. The build is deterministic.

## OG images

If a post has no `og_image` in frontmatter, `scripts/og_image.py` generates
a 1200x630 PNG card with the post title, date, and brand wordmark. Colors
come from `config.py` (`OG_*` fields). A default card is also generated for
the site homepage.

## UTM analytics

Every outbound link (nav CTA, footer, article CTA) is tagged at build time:

- `utm_source` = `config.UTM_SOURCE` (default: `blog`)
- `utm_medium` = `nav`, `footer`, or `article_cta`
- `utm_content` = post slug (only on article CTAs)
- `utm_campaign` = `config.UTM_CAMPAIGN` (optional)

Internal links, assets, RSS, and JSON-LD are never tagged. This lets
analytics platforms attribute outbound clicks to specific articles without
any client-side setup.

## Previewing

Serve `public/` with any static server:

```bash
python3 -m http.server 8000 -d public/
```

On Starchild, use the preview system to serve the built site and get a
shareable URL.

## Publishing

The `public/` directory is static HTML. Deploy to any static host:

- GitHub Pages
- Netlify / Vercel
- Any static file host (rsync, SCP)
- Starchild community publish (via `community-publish` skill)

## Validation checklist

Before publishing a post:

1. `python3 build.py --check` passes with no errors
2. Post has a title and description in frontmatter
3. `draft: false` is set
4. Hero image exists at the path specified in `og_image` (if set)
5. `python3 build.py` completes successfully
6. Preview the post at `/posts/<slug>/` to verify rendering
7. Check `/feed.xml` and `/sitemap.xml` include the post

## Troubleshooting

- **YAML parse error**: usually an unquoted title containing `:` or `#`. Wrap in double quotes.
- **Charts blank**: a CDN `<script src>` slipped back in. Confirm the built page references `vendor/chart.umd.min.js`.
- **Wrong fonts on imported article**: re-run the importer (it forces white bg + blog fonts). Do not patch `public/` by hand.
- **Mojibake**: re-run the importer; it decodes UTF-8 via `apparent_encoding`.
- **"config.py not found" note during build**: not an error; the build used example defaults. Run `cp config.example.py config.py` and edit to customize.
