# Menu Decoder 🍜

## What

Decode any foreign-language restaurant menu from a photo. Extracts all dishes, prices, and descriptions; translates to the user's language; and recommends what to order based on preferences (spice level, budget, dietary restrictions).

Tested on real menus at ICONSIAM, Bangkok (July 2026):
- **LOKA** — Thai creative fried ice cream (6 dishes extracted)
- **Thipsamai** — Legendary Pad Thai with two-step ordering (7 items extracted)

## Required env

No environment variables required. The skill uses the platform's proxied HTTP client (sc-proxy) which auto-injects credentials for the vision model API (OpenRouter → Gemini 3.5 Flash).

## How to start

```python
import sys
sys.path.insert(0, "/data/workspace/skills/menu-decoder")
from exports import decode_menu

result = decode_menu(
    "uploads/menu_photo.jpg",
    language="zh",           # translate to Chinese
    preferences={
        "spice_level": "medium",
        "budget": "moderate",
        "dietary": ["no-shellfish"]
    }
)

print(result["restaurant"])     # "LOKA"
print(result["top_picks"])      # ["蝶蝶豆花糯米榴莲炸冰淇淋", ...]
for dish in result["dishes"]:
    print(f'{dish["translated_name"]} — {dish["price"]} — {dish["recommendation"]}')
```

## Outputs / Behavior

Returns a dict with:
- `success` (bool) — whether decoding succeeded
- `restaurant` (str) — restaurant name if detected
- `language_detected` (str) — source language of the menu
- `dishes` (list) — each dish with: original_name, translated_name, price, description, category, recommendation (★ rating)
- `top_picks` (list) — 2-3 recommended dish names in target language
- `notes` (str) — any important notes (tax, allergens, etc.)

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Image not found" | Check path is workspace-relative (e.g. `uploads/menu.jpg`) |
| API error / 502 | Vision model may be rate-limited; retry after a few seconds |
| JSON parse error | Model returned non-JSON; retry (temperature is set low at 0.3) |
| Wrong language | Pass `language` param: "zh", "en", "ko", "ja", "zh-TW" |

License: MIT
