---
name: menu-decoder
version: 1.0.0
description: |
  Decode any foreign-language restaurant menu from a photo. Extracts all dishes,
  prices, and descriptions; translates to the user's language; and recommends
  what to order based on preferences (spice level, budget, dietary restrictions).

  Use when the user shares a menu photo and asks "what should I order", "what's
  on this menu", "translate this menu", or wants food recommendations from a
  foreign menu image.
metadata:
  starchild:
    emoji: "🍜"
    skillKey: menu-decoder
delivery: script
user-invocable: true
disable-model-invocation: false
---

# Menu Decoder

Take a photo of any restaurant menu → get translated dishes + prices + ordering recommendations.

## How It Works

```
decode_menu(image_path, language="zh", preferences=None)
      │
      ├─ Read image, base64 encode
      ├─ Send to vision model (Gemini 3.5 Flash via OpenRouter)
      │   Prompt: extract ALL dishes, prices, descriptions from the menu
      │   Translate dish names + descriptions to target language
      │   Rate each dish for recommendation (★★★ to ☆)
      ├─ Parse structured JSON response
      └─ Return: restaurant name, language detected, dishes[], top_picks[], notes
```

## Quick Start

```python
import sys
sys.path.insert(0, "/data/workspace/skills/menu-decoder")
from exports import decode_menu

result = decode_menu(
    "uploads/menu_photo.jpg",
    language="zh",           # translate to Chinese
    preferences={             # optional
        "spice_level": "medium",
        "budget": "moderate",
        "dietary": ["no-shellfish"]
    }
)
print(result["restaurant"])     # "Thipsamai"
print(result["top_picks"])      # ["Superb Padthai", "Fresh Orange Juice"]
for dish in result["dishes"]:
    print(f'{dish["translated_name"]} — {dish["price"]} — {dish["recommendation"]}')
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image_path` | str | required | Workspace-relative path to menu photo |
| `language` | str | "zh" | Target language code: zh, en, ko, ja, etc. |
| `preferences` | dict | None | Optional: spice_level, budget, dietary restrictions |

## Response Format

```json
{
  "success": true,
  "restaurant": "Thipsamai",
  "language_detected": "Thai",
  "dishes": [
    {
      "original_name": "ผัดไทยแซ่บ",
      "translated_name": "酸辣泰式炒河粉",
      "price": "219฿",
      "description": "酸辣口味的泰式炒河粉，配大虎虾",
      "category": "main",
      "recommendation": "★★★"
    }
  ],
  "top_picks": ["酸辣泰式炒河粉", "鲜榨橙汁"],
  "notes": "价格不含7%增值税和10%服务费"
}
```

## Agent Behavior

When the user shares a menu photo and asks what to order:
1. Call `decode_menu(image_path, language=<user's language>)`.
2. Present results as a table: dish name → recommendation → price → description.
3. Highlight top picks with ⭐.
4. Include any notes about tax/service charge if detected.
5. Ask about spice tolerance / dietary restrictions if not provided.
