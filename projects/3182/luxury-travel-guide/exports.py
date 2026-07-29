"""luxury-travel-guide skill exports.

Renders an interactive luxury travel guide HTML page from structured data.

Usage:
    python3 - <<'EOF'
    import sys
    sys.path.insert(0, "/data/workspace/skills/luxury-travel-guide")
    from exports import render_guide

    guide = { ... }  # see SKILL.md for data structure
    html = render_guide(guide)

    with open("output/my-city-guide/index.html", "w") as f:
        f.write(html)
    EOF
"""

from __future__ import annotations
from typing import Any

_TAG_CLASS = {
    "pick": "tag-pick",
    "best": "tag-best",
    "deal": "tag-deal",
}


def _stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n)


def _card(venue: dict[str, Any]) -> str:
    name = venue.get("name", "")
    price = venue.get("price", "")
    rating_text = venue.get("rating", "")
    star_count = venue.get("stars", 5)
    address = venue.get("address", "")
    distance = venue.get("distance", "")
    category = venue.get("category", "")
    description = venue.get("description", "")
    tags = venue.get("tags", [])
    highlights = venue.get("highlights", [])
    tip_title = venue.get("tip_title", "")
    tip_text = venue.get("tip_text", "")

    meta_items = ""
    if address:
        meta_items += f'<div class="meta-item">📍 <span>{address}</span></div>'
    if distance:
        meta_items += f'<div class="meta-item">🚶 <span>{distance}</span></div>'
    if category:
        meta_items += f'<div class="meta-item">🍽 <span>{category}</span></div>'

    tags_html = ""
    if tags:
        tags_html = '<div style="margin-bottom:10px;">'
        for tag_type, tag_label in tags:
            cls = _TAG_CLASS.get(tag_type, "tag-deal")
            tags_html += f'<span class="tag {cls}">{tag_label}</span>'
        tags_html += "</div>"

    highlights_html = ""
    if highlights:
        highlights_html = '<ul class="highlights">'
        for item in highlights:
            if len(item) == 3:
                dish, price_str, desc = item
                highlights_html += (
                    f'<li><strong>{dish}</strong> ({price_str}) — {desc}</li>'
                )
            elif len(item) == 2:
                dish, desc = item
                highlights_html += f'<li><strong>{dish}</strong> — {desc}</li>'
            else:
                highlights_html += f"<li>{item[0]}</li>"
        highlights_html += "</ul>"

    tip_html = ""
    if tip_title and tip_text:
        tip_html = (
            f'<div class="tip-box"><h4>{tip_title}</h4><p>{tip_text}</p></div>'
        )

    return f"""  <div class="card">
    <div class="card-header">
      <h3>{name}</h3>
      <div class="price-tag">{price}</div>
    </div>
    <div class="rating">
      <span class="stars">{_stars(star_count)}</span>
      <span class="rating-text">{rating_text}</span>
    </div>
    <div class="meta">{meta_items}</div>
    <p>{description}</p>
    {tags_html}
    {highlights_html}
    {tip_html}
  </div>
"""


def _tips_section(tips: dict[str, Any]) -> str:
    itinerary = tips.get("itinerary", "")
    price_table = tips.get("price_table", [])
    distances = tips.get("distances", [])
    souvenirs = tips.get("souvenirs", [])

    itinerary_html = ""
    if itinerary:
        itinerary_html = f"""  <div class="card">
    <h3 style="margin-bottom:20px;">🎯 Suggested Itinerary</h3>
    <div class="tip-box">
      <h4>Plan</h4>
      <p>{itinerary}</p>
    </div>
  </div>
"""

    price_table_html = ""
    if price_table:
        rows = ""
        for row in price_table:
            cells = "".join(
                f'<td style="padding:10px 0; {"color:var(--text-dim);" if i == 0 else ""}">{cell}</td>'
                for i, cell in enumerate(row)
            )
            rows += f'<tr style="border-bottom:1px solid rgba(255,255,255,0.05);">{cells}</tr>'
        price_table_html = f"""  <div class="card">
    <h3 style="margin-bottom:16px;">💰 Price Tiers at a Glance</h3>
    <table style="width:100%; border-collapse:collapse; font-size:0.9rem;">
      <tr style="border-bottom:1px solid var(--border);">
        <th style="text-align:left; padding:10px 0; color:var(--gold);">Category</th>
        <th style="text-align:left; padding:10px 0; color:var(--gold);">Budget</th>
        <th style="text-align:left; padding:10px 0; color:var(--gold);">Mid</th>
        <th style="text-align:left; padding:10px 0; color:var(--gold);">Ultra-Luxury</th>
      </tr>
      {rows}
    </table>
  </div>
"""

    distances_html = ""
    if distances:
        items = "".join(
            f"<li><strong>{name}</strong> — {dist}</li>" for name, dist in distances
        )
        distances_html = f"""  <div class="card">
    <h3 style="margin-bottom:16px;">📍 Distance Reference</h3>
    <ul class="highlights">{items}</ul>
  </div>
"""

    souvenirs_html = ""
    if souvenirs:
        items = "".join(
            f"<li><strong>{name}</strong> — {desc}</li>" for name, desc in souvenirs
        )
        souvenirs_html = f"""  <div class="card">
    <h3 style="margin-bottom:16px;">🎁 Souvenir Picks</h3>
    <ul class="highlights">{items}</ul>
  </div>
"""

    return itinerary_html + price_table_html + distances_html + souvenirs_html


def render_guide(guide: dict[str, Any]) -> str:
    """Render a luxury travel guide HTML page from structured data.

    Args:
        guide: Dict with keys: city, subtitle, badge, dining, spa, omakase, tips.
            Each venue is a dict with: name, price, rating, stars, address,
            distance, category, description, tags, highlights, tip_title, tip_text.
            tips is a dict with: itinerary, price_table, distances, souvenirs.

    Returns:
        Complete HTML string for a single-file interactive guide.
    """
    city = guide.get("city", "City")
    subtitle = guide.get("subtitle", "Luxury Guide")
    badge = guide.get("badge", "")
    dining = guide.get("dining", [])
    spa = guide.get("spa", [])
    omakase = guide.get("omakase", [])
    tips = guide.get("tips", {})

    dining_cards = "".join(_card(v) for v in dining)
    spa_cards = "".join(_card(v) for v in spa)
    omakase_cards = "".join(_card(v) for v in omakase)
    tips_html = _tips_section(tips)

    # Hide omakase tab if empty
    omakase_tab_btn = ""
    omakase_panel = ""
    if omakase:
        omakase_tab_btn = '<button class="tab-btn" onclick="switchTab(\'omakase\')">🍣 Omakase</button>'
        omakase_panel = f'<div class="tab-panel" id="omakase">{omakase_cards}</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{city} — {subtitle}</title>
<style>
:root {{
  --gold: #C5A572;
  --gold-light: #E8D5B0;
  --dark: #1A1A2E;
  --dark-2: #16213E;
  --card: #1E2A45;
  --card-hover: #243352;
  --text: #E8E8E8;
  --text-dim: #9CA3B8;
  --accent: #E94560;
  --green: #4ECCA3;
  --border: rgba(197,165,114,0.2);
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: 'Georgia', 'Noto Serif', serif; background: var(--dark); color: var(--text); min-height: 100vh; }}
.hero {{
  background: linear-gradient(135deg, #0F3460 0%, #1A1A2E 50%, #16213E 100%);
  padding: 60px 20px 50px; text-align: center; position: relative; overflow: hidden;
}}
.hero::before {{ content: '🏛'; position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); font-size: 280px; opacity: 0.04; }}
.hero h1 {{
  font-size: 2.6rem; background: linear-gradient(135deg, var(--gold), var(--gold-light));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: 2px; margin-bottom: 12px;
}}
.hero p {{ color: var(--text-dim); font-size: 1.05rem; max-width: 600px; margin: 0 auto; line-height: 1.6; }}
.hero .badge {{
  display: inline-block; margin-top: 18px; padding: 6px 18px; border: 1px solid var(--gold);
  border-radius: 20px; color: var(--gold); font-size: 0.8rem; letter-spacing: 1px; text-transform: uppercase;
}}
.tabs {{ display: flex; justify-content: center; gap: 8px; padding: 24px 20px 0; background: var(--dark-2); flex-wrap: wrap; }}
.tab-btn {{
  padding: 12px 28px; background: transparent; border: 1px solid var(--border); color: var(--text-dim);
  border-radius: 12px 12px 0 0; cursor: pointer; font-size: 0.95rem; font-family: inherit; transition: all 0.3s; border-bottom: none;
}}
.tab-btn:hover {{ color: var(--gold); border-color: var(--gold); }}
.tab-btn.active {{ background: var(--card); color: var(--gold); border-color: var(--gold); }}
.content {{ padding: 0 20px 60px; max-width: 960px; margin: 0 auto; }}
.tab-panel {{ display: none; }}
.tab-panel.active {{ display: block; animation: fadeIn 0.4s; }}
@keyframes fadeIn {{ from {{ opacity:0; transform:translateY(10px); }} to {{ opacity:1; transform:translateY(0); }} }}
.card {{
  background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 28px; margin-bottom: 20px; transition: all 0.3s;
}}
.card:hover {{ background: var(--card-hover); border-color: rgba(197,165,114,0.4); }}
.card-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }}
.card h3 {{ font-size: 1.4rem; color: var(--gold); }}
.card .price-tag {{ font-size: 1.1rem; color: var(--green); font-weight: bold; white-space: nowrap; }}
.card .rating {{ display: flex; align-items: center; gap: 6px; margin-bottom: 12px; }}
.stars {{ color: var(--gold); letter-spacing: 2px; }}
.rating-text {{ color: var(--text-dim); font-size: 0.85rem; }}
.card p {{ color: var(--text-dim); line-height: 1.7; margin-bottom: 14px; }}
.card .meta {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 14px; }}
.meta-item {{ display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: var(--text-dim); }}
.meta-item span {{ color: var(--gold); }}
.highlights {{ list-style: none; }}
.highlights li {{ padding: 8px 0 8px 24px; color: var(--text); font-size: 0.92rem; border-bottom: 1px solid rgba(255,255,255,0.05); position: relative; }}
.highlights li:last-child {{ border-bottom: none; }}
.highlights li::before {{ content: '✦'; position: absolute; left: 0; color: var(--gold); }}
.tag {{ display: inline-block; padding: 3px 10px; border-radius: 6px; font-size: 0.75rem; margin-right: 6px; margin-bottom: 4px; }}
.tag-pick {{ background: rgba(228,69,96,0.15); color: var(--accent); border: 1px solid rgba(228,69,96,0.3); }}
.tag-best {{ background: rgba(78,204,163,0.15); color: var(--green); border: 1px solid rgba(78,204,163,0.3); }}
.tag-deal {{ background: rgba(197,165,114,0.15); color: var(--gold); border: 1px solid rgba(197,165,114,0.3); }}
.tip-box {{
  background: linear-gradient(135deg, rgba(197,165,114,0.08), rgba(228,69,96,0.05));
  border: 1px solid var(--border); border-radius: 12px; padding: 20px 24px; margin: 24px 0;
}}
.tip-box h4 {{ color: var(--gold); font-size: 1rem; margin-bottom: 8px; }}
.tip-box p {{ color: var(--text-dim); font-size: 0.9rem; line-height: 1.6; margin: 0; }}
.footer {{ text-align: center; padding: 30px 20px; color: var(--text-dim); font-size: 0.8rem; border-top: 1px solid var(--border); }}
.footer a {{ color: var(--gold); text-decoration: none; }}
@media (max-width: 600px) {{
  .hero h1 {{ font-size: 1.8rem; }}
  .card {{ padding: 20px; }}
  .tab-btn {{ padding: 10px 16px; font-size: 0.85rem; }}
}}
</style>
</head>
<body>

<div class="hero">
  <h1>{city.upper()}</h1>
  <p>{subtitle}</p>
  <div class="badge">{badge}</div>
</div>

<div class="tabs">
  <button class="tab-btn active" onclick="switchTab('dining')">🍽 Fine Dining</button>
  <button class="tab-btn" onclick="switchTab('spa')">🧖 Spa & Wellness</button>
  {omakase_tab_btn}
  <button class="tab-btn" onclick="switchTab('tips')">💡 Pro Tips</button>
</div>

<div class="content">
  <div class="tab-panel active" id="dining">{dining_cards}</div>
  <div class="tab-panel" id="spa">{spa_cards}</div>
  {omakase_panel}
  <div class="tab-panel" id="tips">{tips_html}</div>
</div>

<div class="footer">
  {city} Luxury Guide · Built with <a href="#">Agentway</a>
</div>

<script>
function switchTab(id) {{
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById(id).classList.add('active');
}}
</script>

</body>
</html>"""
