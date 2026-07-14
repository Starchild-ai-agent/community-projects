"""Branded Open Graph card generator.

Renders 1200x630 PNG cards with a colored accent bar, the post title in
Google Sans bold, the publication date, and an icon + wordmark in the
bottom-left corner. Colors and wordmark text are read from config.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent.parent
ASSETS_DIR = ROOT / "assets"
FONT_PATH = ASSETS_DIR / "fonts" / "GoogleSans-Bold.ttf"
ICON_PATH = ASSETS_DIR / "icon.png"

CARD_W, CARD_H = 1200, 630

# Load brand colors from config by explicit file path (a bare `import config`
# can be shadowed by unrelated packages on sys.path). Falls back to
# config.example.py so the generator works on a fresh fork.
import importlib.util  # noqa: E402

_cfg_path = ROOT / "config.py"
if not _cfg_path.exists():
    _cfg_path = ROOT / "config.example.py"
_spec = importlib.util.spec_from_file_location("blog_config_og", _cfg_path)
config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(config)

BG_COLOR = getattr(config, "OG_BG_COLOR", (255, 255, 255))
BAR_COLOR = getattr(config, "OG_BAR_COLOR", (248, 70, 0))
TEXT_COLOR = getattr(config, "OG_TEXT_COLOR", (21, 21, 21))
DATE_COLOR = getattr(config, "OG_DATE_COLOR", (107, 107, 107))
BRAND_COLOR = getattr(config, "OG_BRAND_COLOR", (248, 70, 0))
WORDMARK_TEXT = getattr(config, "OG_WORDMARK_TEXT", "Blog")

BAR_H = 12
MARGIN = 60
MAX_TEXT_W = CARD_W - 2 * MARGIN  # 1080
MAX_TITLE_LINES = 4
TITLE_START_PX = 72
TITLE_MIN_PX = 36
DATE_PX = 28
ICON_PX = 80
BOTTOM_RESERVED = ICON_PX + 24  # icon + breathing room from the bottom

# Variable font axes order: GRAD, opsz, wght. We want a heavy bold weight.
_WGHT_AXES = (0.0, 16.0, 700.0)


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(FONT_PATH), size)
    try:
        font.set_variation_by_axes(list(_WGHT_AXES))
    except (AttributeError, Exception):  # noqa: BLE001
        # Variation axes not supported by this build of Pillow / freetype;
        # fall back to the default weight.
        pass
    return font


def _wrap_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont,
                    max_w: int) -> list[str]:
    """Greedy word-wrap that respects the rendered pixel width."""
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for w in words[1:]:
        candidate = f"{current} {w}"
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_w:
            current = candidate
        else:
            lines.append(current)
            current = w
    lines.append(current)
    return lines


def _fit_title(draw: ImageDraw.ImageDraw, title: str) -> tuple[ImageFont.ImageFont, list[str]]:
    """Shrink the title font until it fits within MAX_TITLE_LINES at MAX_TEXT_W."""
    size = TITLE_START_PX
    while size >= TITLE_MIN_PX:
        font = _load_font(size)
        lines = _wrap_to_width(draw, title, font, MAX_TEXT_W)
        if len(lines) <= MAX_TITLE_LINES:
            return font, lines
        size -= 4
    # Last resort: clamp to MAX_TITLE_LINES lines at the smallest size.
    font = _load_font(TITLE_MIN_PX)
    lines = _wrap_to_width(draw, title, font, MAX_TEXT_W)
    return font, lines[:MAX_TITLE_LINES]


def generate_og(title: str, date: str, out_path: str) -> None:
    """Render a 1200x630 OG card to ``out_path``.

    ``title`` is the headline; ``date`` is the small caption line drawn
    beneath it (a tagline works equally well, e.g. for the site default).
    """
    img = Image.new("RGB", (CARD_W, CARD_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Top brand bar.
    draw.rectangle([(0, 0), (CARD_W, BAR_H)], fill=BAR_COLOR)

    # Title + date.
    title_font, title_lines = _fit_title(draw, title)
    line_height = title_font.size + 8
    title_block_h = line_height * len(title_lines)
    # Vertical position: top-anchored with a comfortable gap under the bar.
    title_y = BAR_H + 60
    for i, line in enumerate(title_lines):
        draw.text((MARGIN, title_y + i * line_height), line,
                  fill=TEXT_COLOR, font=title_font)

    date_font = _load_font(DATE_PX)
    date_y = title_y + title_block_h + 16
    draw.text((MARGIN, date_y), date, fill=DATE_COLOR, font=date_font)

    # Bottom-left: icon + wordmark.
    icon = Image.open(ICON_PATH).convert("RGBA")
    icon = icon.resize((ICON_PX, ICON_PX), Image.LANCZOS)
    icon_y = CARD_H - ICON_PX - 36
    img.paste(icon, (MARGIN, icon_y), icon)

    wordmark_font = _load_font(28)
    wordmark = WORDMARK_TEXT
    wordmark_x = MARGIN + ICON_PX + 16
    bbox = draw.textbbox((0, 0), wordmark, font=wordmark_font)
    text_h = bbox[3] - bbox[1]
    wordmark_y = icon_y + (ICON_PX - text_h) // 2 - bbox[1]
    draw.text((wordmark_x, wordmark_y), wordmark,
              fill=BRAND_COLOR, font=wordmark_font)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, format="PNG", optimize=True)
