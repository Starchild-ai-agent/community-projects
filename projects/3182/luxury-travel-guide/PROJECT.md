# Luxury Travel Guide Generator

Turn curated dining/spa/lifestyle research into a polished interactive web app.

## What it produces

A single-file `index.html` with:
- Dark + gold luxury theme (Georgia serif, card layout)
- 4 tabs: Fine Dining · Spa & Wellness · Omakase · Pro Tips
- Per-venue cards: name, price, rating, address, distance, highlights, tip boxes
- Price tier comparison table + distance reference + souvenir picks
- Mobile responsive

## Required env

No environment variables required. `render_guide()` is a pure HTML template function.

## How to start

```python
import sys
sys.path.insert(0, "/data/workspace/skills/luxury-travel-guide")
from exports import render_guide

guide = {
    "city": "Phnom Penh",
    "subtitle": "Luxury Guide — Dining, Spa & Beyond",
    "badge": "Curated · July 2026",
    "dining": [
        {
            "name": "Topaz Norodom",
            "price": "~$50-60/person",
            "rating": "4.6/5 · 50 Best Discovery",
            "stars": 5,
            "address": "162 Norodom Blvd",
            "distance": "5 min from Raffles",
            "category": "French Fine Dining",
            "description": "...",
            "tags": [("best", "Editor's Pick")],
            "highlights": [("Dish", "$18", "Description")],
            "tip_title": "Booking Tip",
            "tip_text": "Request courtyard table.",
        },
    ],
    "spa": [...],
    "omakase": [...],
    "tips": {
        "itinerary": "14:00 Killing Fields → 16:00 Spa → 19:00 Dinner",
        "price_table": [("Dining", "Sombok ~$30", "Topaz ~$55", "KYŌ $278")],
        "distances": [("Topaz Norodom", "5 min walk")],
        "souvenirs": [("Soursop Dates", "~$2.20/pack")],
    },
}
html = render_guide(guide)

with open("output/my-city-guide/index.html", "w") as f:
    f.write(html)
```

Then publish:
```python
# preview(action="serve", dir="output/my-city-guide", title="City Luxury Guide")
# from skills.community_publish.exports import publish_preview, list_in_dashboard
# publish_preview("your-slug")
# list_in_dashboard(slug="your-slug", name="...", tags=["travel", "luxury"])
```

## Outputs / Behavior

- `render_guide(guide: dict) -> str` — returns complete HTML string
- Output is a single self-contained `index.html` (no external dependencies)
- Omakase tab auto-hides if no omakase venues provided
- Tag types: `pick` (red), `best` (green), `deal` (gold)

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError` | Ensure `sys.path.insert(0, "/data/workspace/skills/luxury-travel-guide")` before import |
| Empty omakase tab | Omakase tab auto-hides when `guide["omakase"]` is empty — this is by design |
| Tags not rendering | Tag type must be one of: `pick`, `best`, `deal` |

## License

MIT
