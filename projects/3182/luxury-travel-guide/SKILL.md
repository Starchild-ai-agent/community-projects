---
name: luxury-travel-guide
version: 1.0.0
description: |
  Generate interactive luxury travel guide web apps for any city — fine dining,
  spa & wellness, omakase, and pro tips, rendered as a tabbed HTML page with
  dark-gold luxury theme. Includes research workflow, HTML template, and render
  function. Publish the result as a preview + public URL.
author: starchild
tags: [travel, luxury, guide, html, template]
delivery: script
metadata:
  starchild:
    emoji: 🏛
    skillKey: luxury-travel-guide
---

# 🏛 Luxury Travel Guide Generator

Turn curated dining/spa/lifestyle research into a polished interactive web app.

## What it produces

A single-file `index.html` with:
- Dark + gold luxury theme (Georgia serif, card layout)
- 4 tabs: Fine Dining · Spa & Wellness · Omakase · Pro Tips
- Per-venue cards: name, price, rating, address, distance, highlights, tip boxes
- Price tier comparison table + distance reference + souvenir picks
- Mobile responsive

## Workflow

1. **Research** — `web_search` + `web_fetch` for each category:
   - Fine dining (TripAdvisor + 50 Best Discovery + local sources)
   - Spa (TripAdvisor + hotel spa menus + reviews)
   - Omakase (if applicable — not every city is an omakase destination)
   - Pro tips (distances, price tiers, itinerary, souvenirs)
2. **Structure data** — organize into the 4 categories with the fields below
3. **Render** — call `render_guide()` from `exports.py` to produce HTML
4. **Publish** — `preview(action="serve")` → `publish_preview()` → `list_in_dashboard()`

## Data structure

```python
guide = {
    "city": "Phnom Penh",
    "subtitle": "Luxury Guide — Dining, Spa & Beyond",
    "badge": "Curated · July 2026",
    "dining": [
        {
            "name": "Topaz Norodom",
            "price": "~$50-60/person",
            "rating": "4.6/5 · 1,045 reviews · 50 Best Discovery",
            "stars": 5,
            "address": "162 Norodom Blvd",
            "distance": "5 min from Raffles",
            "category": "French Fine Dining",
            "description": "Phnom Penh's grand dame of French cuisine since 1997...",
            "tags": [("pick", "Editor's Pick"), ("best", "50 Best Discovery")],
            "highlights": [
                ("Élysée Truffle Soup", "~$18", "Double beef consommé + black winter truffle + foie gras."),
                # ... more items
            ],
            "tip_title": "Booking Tip",
            "tip_text": "Request courtyard table under the Banyan tree.",
        },
        # ... more restaurants
    ],
    "spa": [ ... ],      # same structure
    "omakase": [ ... ],  # same structure
    "tips": {
        "itinerary": "14:00 Killing Fields → 16:00 Spa → 19:00 Topaz → 22:00 Nightcap",
        "price_table": [
            ("Dining", "Sombok ~$30", "Topaz ~$55", "KYŌ $278"),
            ("Spa", "Samatha ~$35", "Raffles ~$110", "Rosewood ~$200"),
        ],
        "distances": [
            ("Samatha Spa", "5 min walk"),
            ("Topaz Norodom", "5 min walk"),
        ],
        "souvenirs": [
            ("Raffles Krama", "Complimentary Khmer scarf at checkout."),
            ("Soursop Dates", "~$2.20/pack at local supermarkets."),
        ],
    },
}
```

## Render

```bash
python3 - <<'EOF'
import sys, json
sys.path.insert(0, "/data/workspace/skills/luxury-travel-guide")
from exports import render_guide

guide = { ... }  # your data structure
html = render_guide(guide)

with open("output/my-city-guide/index.html", "w") as f:
    f.write(html)
print("Guide rendered to output/my-city-guide/index.html")
EOF
```

## Publish

```python
# 1. Serve as preview
# preview(action="serve", dir="output/my-city-guide", title="City Luxury Guide")

# 2. Get public URL
sys.path.insert(0, "/data/workspace/skills/community-publish")
from exports import publish_preview, list_in_dashboard
publish_preview("your-preview-slug")
list_in_dashboard(
    slug="your-preview-slug",
    name="City Luxury Guide — Dining, Spa & Beyond",
    description="Interactive curated guide...",
    tags=["travel", "luxury", "dining", "spa"]
)
```

## Tag types

| Tag class | Color | Use |
|-----------|-------|-----|
| `pick` | Red | Editor's pick / special mention |
| `best` | Green | Best in category / #1 |
| `deal` | Gold | Best value |

## Tips for great guides

- **Honest takes sell** — include "should you even do X in this city?" sections
- **Distance from a landmark hotel** is the most useful navigation aid
- **Price tiers** (budget / mid / ultra-luxury) help readers self-select
- **Specific dish recommendations** with prices beat generic "great food" reviews
- **Souvenir picks** with actual prices add practical value
- Always cite sources (TripAdvisor, 50 Best, local publications)
