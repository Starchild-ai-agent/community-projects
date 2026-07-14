# Blog Template

## What

A fully functioning blog platform managed by your Starchild agent. Static site generator in ~1,000 lines of readable Python, no framework, no database. Ships with: markdown posts with a draft/publish workflow, RSS (site-wide + per tag), XML sitemap, robots.txt, JSON-LD structured data, canonical URLs, auto-generated Open Graph card images, build-time UTM tagging of outbound links, an HTML article importer that turns any URL into a formatted draft, and a JSON API of posts.

Quick start for users: paste this to your agent.

> Fork 1892/blog-template, set it up with my brand, and publish our first blog article.

`AGENT.md` in this repo is the operating manual your agent follows (build commands, frontmatter reference, draft workflow, import tools, pre-publish checklist).

## Required env

None. All site settings live in `config.py` (copy `config.example.py` and edit). The build falls back to `config.example.py` defaults so a fresh fork builds with zero setup.

`scripts/import_article.py` uses the Starchild container's `core.http_client` for fetching URLs, which is available in every agent workspace and needs no keys.

## How to start

```bash
pip install -r requirements.txt   # markdown + Pillow
python3 build.py                  # builds the site into public/
python3 -m http.server 8765 -d public/
```

Optional flags: `python3 build.py --check` (validate without writing), `python3 build.py --drafts` (include drafts on the homepage for preview).

To customize: `cp config.example.py config.py`, then edit site name, URL, tagline, CTA, and brand colors. Replace the logo files in `assets/` and the CSS variables in the `:root` block of `assets/style.css`.

## Outputs

- `public/` — the complete static site (HTML, RSS at `feed.xml`, `sitemap.xml`, `robots.txt`, OG card PNGs under `assets/og/`, post JSON at `api/posts.json`). Self-contained; deploy anywhere or serve with the Starchild preview tool.
- Build log line, e.g. `built 1 post(s), 0 draft(s), 2 tag(s)`.

## Troubleshooting

- **"config.py not found" note during build**: not an error; the build used `config.example.py` defaults. Copy it to `config.py` to customize.
- **Draft not on homepage**: intended. Drafts render to `/drafts/<slug>/` only. Set `draft: false` and rebuild to publish, or use `--drafts` to preview inline.
- **OG images not regenerating**: cards are cached in `public/og/` and preserved across builds. Delete the stale PNG and rebuild.
- **Import produced messy markup**: the importer scopes the source page's CSS so it cannot break the site, but complex pages may need manual cleanup of the generated markdown in `content/posts/`.
- **Fonts look wrong after replacing**: update both `@font-face` rules in `assets/style.css` and `FONT_PATH` in `scripts/og_image.py` (Pillow needs a static TTF, not woff2).
