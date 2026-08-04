"""
Pack Studio - Listing Copy Generator

Generates Gumroad-style listing copy (title, subtitle, description,
features, benefits, CTA) for a finished product pack.
"""

import json
import re
from typing import Any, Dict, List

from .brief import ProductBrief
from .content import chat

LISTING_SYSTEM_PROMPT = (
    "You are an expert copywriter for Gumroad-style digital product listings. "
    "Write benefit-driven, professional marketing copy matching the requested tone. "
    "Never mention you are an AI. If a real product link is not given, use the literal "
    "placeholder text [LINK] in the CTA rather than inventing a URL. "
    "Respond with ONLY a JSON object, no surrounding text, matching this shape: "
    '{"title": str, "subtitle": str, "description": str, "features": [str, ...], '
    '"benefits": [str, ...], "cta": str}'
)


def _extract_json(raw: str) -> Dict[str, Any]:
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model response")
    return json.loads(match.group(0))


def _coerce_str_list(value: Any) -> List[str]:
    """The prompt asks for a list, but small local models sometimes return a
    single string (or something else) instead -- coerce rather than letting
    downstream code silently iterate a string character-by-character."""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_listing_data(data: Dict[str, Any], product_brief: ProductBrief) -> Dict[str, Any]:
    return {
        "title": str(data.get("title") or product_brief.title),
        "subtitle": str(data.get("subtitle") or ""),
        "description": str(data.get("description") or ""),
        "features": _coerce_str_list(data.get("features")),
        "benefits": _coerce_str_list(data.get("benefits")),
        "cta": str(data.get("cta") or ""),
    }


def generate_listing_copy(product_brief: ProductBrief, content_summary: str, model: str) -> Dict[str, Any]:
    user_prompt = (
        f"{product_brief.context_block()}\n\n"
        f"Content summary:\n{content_summary[:2000]}\n\n"
        "Generate the listing JSON described in the system prompt. "
        "Title max 80 chars, subtitle max 200 chars, description under 800 words, "
        "5-7 features, 3-5 benefits, one strong CTA."
    )
    messages = [
        {"role": "system", "content": LISTING_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    raw = chat(messages, model=model, temperature=0.8, max_tokens=1200)

    try:
        data = _normalize_listing_data(_extract_json(raw), product_brief)
    except (ValueError, json.JSONDecodeError):
        # Fall back to the raw text as the description so nothing is lost
        data = {
            "title": product_brief.title,
            "subtitle": "",
            "description": raw,
            "features": [],
            "benefits": [],
            "cta": "Get instant access now: [LINK]",
        }

    data["cta"] = product_brief.apply_link(data["cta"])
    data["description"] = product_brief.apply_link(data["description"])
    return data


def render_listing_markdown(listing_data: Dict[str, Any]) -> str:
    parts = [f"# {listing_data.get('title', '')}", ""]
    if listing_data.get("subtitle"):
        parts += [f"## {listing_data['subtitle']}", ""]
    if listing_data.get("description"):
        parts += ["## Description", "", str(listing_data["description"]), ""]
    if listing_data.get("features"):
        parts += ["## Features", ""]
        parts += [f"- {f}" for f in listing_data["features"]]
        parts.append("")
    if listing_data.get("benefits"):
        parts += ["## Benefits", ""]
        parts += [f"- {b}" for b in listing_data["benefits"]]
        parts.append("")
    if listing_data.get("cta"):
        parts += ["## Call to Action", "", f"**{listing_data['cta']}**", ""]
    return "\n".join(parts)
