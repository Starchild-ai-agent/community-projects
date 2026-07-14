# Agent Blog Template

A fully functioning blog platform managed by your Starchild agent. Fork it from the Projects tab, tell your agent what to write, and everything else (formatting, SEO, social cards, RSS, publishing) is handled.

## What This Is

A static site generator in ~1,000 lines of readable Python. No framework, no database, no runtime dependencies. Your agent writes markdown, runs `python3 build.py`, and gets a self-contained `public/` directory ready to publish.

Built-in and working out of the box:

- Markdown posts with a draft/publish workflow
- RSS feed (site-wide and per tag), XML sitemap, robots.txt
- JSON-LD structured data, canonical URLs, meta descriptions
- Open Graph cards auto-generated from post titles
- UTM-tagged outbound links for per-article click attribution
- HTML article importer (any URL becomes a formatted draft)
- JSON API of posts (`/api/posts.json`)
- Vendored Chart.js for posts with charts (no CDN)

## Quick Start (Starchild)

Paste this to your agent:

> Fork 1892-blog-template, set it up with my brand, and publish our first blog article.

That's the whole setup. Your agent forks the code, reads `AGENT.md` (the operating manual in this repo), configures the site, and sends you a preview to approve.

## Quick Start (Manual)

```bash
pip install -r requirements.txt
python3 build.py                      # builds with example config
python3 -m http.server 8000 -d public/
```

The build works with zero setup using `config.example.py` defaults. To customize:

```bash
cp config.example.py config.py
# edit config.py: site name, URL, tagline, CTA, brand colors
python3 build.py
```

## Writing a Post

Create `content/posts/YYYY-MM-DD-slug.md`:

```yaml
---
title: "My First Post"
date: 2026-01-15
description: "A short summary for SEO."
tags: [announcements]
draft: true
---

Write your markdown here.
```

Drafts render to `/drafts/<slug>/` for preview and stay out of the homepage, RSS, and sitemap. Set `draft: false` and rebuild to publish. Use `python3 build.py --drafts` to preview drafts on the homepage.

## Importing an Article

```bash
python3 scripts/import_article.py "https://example.com/article" \
    --date 2026-01-15 --slug my-article --title "Title" --tags a,b
```

Fetches the page, extracts content, scopes CSS so it cannot leak into the site design, and writes a draft.

## Customizing

- **Site settings**: `config.py` (copy from `config.example.py`)
- **Colors**: CSS variables in the `:root` block of `assets/style.css`
- **Social card colors**: `OG_*` values in `config.py`
- **Logo/icon**: replace `assets/icon.png`, `assets/icon.svg`, `assets/wordmark.svg`
- **Fonts**: swap files in `assets/fonts/`, update `@font-face` in `style.css`

## Project Structure

```
config.example.py          site settings template (copy to config.py)
build.py                   the generator: python3 build.py [--check|--drafts]
AGENT.md                   operating manual for your Starchild agent
scripts/                   article importer, OG card generator
templates/                 4 HTML templates (string.Template)
assets/                    CSS, fonts, logos, vendored JS
content/posts/             your articles, one markdown file each
public/                    build output (gitignored)
```

## License

MIT
