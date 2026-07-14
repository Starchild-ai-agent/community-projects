"""Single source of truth for site-wide constants.

Copy this file to config.py and edit the values for your blog.
Then run: python3 build.py

Nothing else needs to change when you rebrand or move hosts.
Absolute URLs (canonical, og:url, JSON-LD) are derived from SITE_URL at
build time; internal links and asset references stay relative so the
output works under any base path.
"""

# Public site URL (no trailing slash on the host portion, trailing slash on the
# base path so it concatenates cleanly with /posts/<slug>/, /tags/<tag>/, etc.)
SITE_URL = "https://example.com/blog"

# Brand / identity
SITE_NAME = "Your Blog"
SITE_TAGLINE = "Thoughts, announcements, and ideas from your team."
DEFAULT_AUTHOR = "Your Name"
SITE_DESCRIPTION = (
    "Your blog description goes here. Keep it under 160 characters for SEO."
)

# Brand assets referenced by JSON-LD and favicons (absolute URLs derived from
# SITE_URL at build time; the path-on-host is fixed here).
ICON_PATH = "/assets/icon.png"
WORDMARK_PATH = "/assets/wordmark.svg"

# Call-to-action button shown in the nav and at the bottom of each post.
# UTM params are appended at build time via build._utm_url so every outbound
# marketing link is tagged consistently.
CTA_URL = "https://example.com"
CTA_TEXT = "Get Started"
ORG_URL = "https://example.com"

# UTM scheme for outbound marketing links (nav, footer, article CTA).
# Internal blog links, assets, RSS, and JSON-LD stay untagged.
UTM_SOURCE = "blog"
# medium values in use: nav, footer, article_cta
# campaign is optional; leave empty unless a named campaign is live.
UTM_CAMPAIGN = ""

# OG image generator brand colors (used by scripts/og_image.py)
# Must be RGB tuples.
OG_BG_COLOR = (255, 255, 255)
OG_BAR_COLOR = (248, 70, 0)       # top accent bar
OG_TEXT_COLOR = (21, 21, 21)
OG_DATE_COLOR = (107, 107, 107)
OG_BRAND_COLOR = (248, 70, 0)

# Wordmark text shown in the bottom-left of OG cards
OG_WORDMARK_TEXT = "Your Blog"
