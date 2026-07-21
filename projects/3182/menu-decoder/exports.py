"""menu-decoder skill exports.

Decode any foreign-language restaurant menu from a photo:
extract dishes, prices, descriptions; translate; recommend.
"""
from __future__ import annotations

import base64
import json
import os
import sys

from core.http_client import proxied_post

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_SKILL_DIR, "config", "menu-decoder.yaml")

# Lazy config load
_config = None


def _load_config():
    global _config
    if _config is not None:
        return _config
    try:
        import yaml
        with open(_CONFIG_PATH, "r") as f:
            _config = yaml.safe_load(f)
    except Exception:
        _config = {}
    return _config


def _get_model():
    cfg = _load_config()
    return cfg.get("model", "google/gemini-3.5-flash")


def _get_caller_id():
    cfg = _load_config()
    return cfg.get("caller_id", "chat:menu-decoder")


def _build_prompt(language: str, preferences: dict | None) -> str:
    pref_text = ""
    if preferences:
        parts = []
        if "spice_level" in preferences:
            parts.append(f"Spice tolerance: {preferences['spice_level']}")
        if "budget" in preferences:
            parts.append(f"Budget: {preferences['budget']}")
        if "dietary" in preferences:
            parts.append(f"Dietary restrictions: {', '.join(preferences['dietary'])}")
        if parts:
            pref_text = f"\n\nUser preferences: {'; '.join(parts)}. Factor these into recommendations."

    lang_names = {
        "zh": "Chinese (Simplified)",
        "en": "English",
        "ko": "Korean",
        "ja": "Japanese",
        "zh-TW": "Chinese (Traditional)",
    }
    lang_name = lang_names.get(language, language)

    return f"""You are a food expert and menu translator. Analyze this restaurant menu image carefully.

Extract ALL visible dishes, drinks, and items. For each item, provide:
1. original_name: The name as written on the menu (in the original language)
2. translated_name: Translated to {lang_name}
3. price: The price as shown (include currency symbol)
4. description: A brief description of what the dish is, in {lang_name}
5. category: One of "main", "dessert", "drink", "side", "topping", "set_menu"
6. recommendation: Your rating from ★ to ★★★★★ based on how good/unique/worth-trying it is

Also identify:
- restaurant: The restaurant name if visible
- language_detected: What language the menu is in
- top_picks: 2-3 dish names (in {lang_name}) you most recommend
- notes: Any important notes (tax not included, allergen warnings, etc.){pref_text}

Respond as valid JSON ONLY (no markdown, no explanation). Use this exact structure:
{{
  "restaurant": "string",
  "language_detected": "string",
  "dishes": [
    {{
      "original_name": "string",
      "translated_name": "string",
      "price": "string",
      "description": "string",
      "category": "string",
      "recommendation": "string"
    }}
  ],
  "top_picks": ["string"],
  "notes": "string"
}}"""


def decode_menu(
    image_path: str,
    language: str = "zh",
    preferences: dict | None = None,
) -> dict:
    """Decode a foreign-language menu photo into translated dishes + recommendations.

    Args:
        image_path: Workspace-relative path to the menu image.
        language: Target language code (zh, en, ko, ja, etc.).
        preferences: Optional dict with spice_level, budget, dietary list.

    Returns:
        Dict with success, restaurant, language_detected, dishes, top_picks, notes.
    """
    # Resolve path
    if not os.path.isabs(image_path):
        full_path = os.path.join("/data/workspace", image_path)
    else:
        full_path = image_path

    if not os.path.exists(full_path):
        return {
            "success": False,
            "error": f"Image not found: {image_path}",
            "dishes": [],
            "top_picks": [],
            "notes": "",
        }

    # Read and encode image
    with open(full_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    # Detect mime type
    ext = os.path.splitext(full_path)[1].lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
    mime = mime_map.get(ext, "image/jpeg")

    # Build request
    prompt = _build_prompt(language, preferences)
    payload = {
        "model": _get_model(),
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                ],
            }
        ],
        "max_tokens": 4000,
        "temperature": 0.3,
    }

    headers = {"SC-CALLER-ID": _get_caller_id(), "Content-Type": "application/json"}

    try:
        resp = proxied_post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
        )
        data = resp.json()

        if "choices" not in data:
            return {
                "success": False,
                "error": f"API error: {json.dumps(data, ensure_ascii=False)[:500]}",
                "dishes": [],
                "top_picks": [],
                "notes": "",
            }

        content = data["choices"][0]["message"]["content"]

        # Parse JSON from response (handle markdown code blocks)
        content = content.strip()
        if content.startswith("```"):
            # Remove markdown code fences
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        result = json.loads(content)
        result["success"] = True
        return result

    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Failed to parse JSON response: {e}",
            "raw_response": content[:500] if "content" in dir() else "",
            "dishes": [],
            "top_picks": [],
            "notes": "",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "dishes": [],
            "top_picks": [],
            "notes": "",
        }
