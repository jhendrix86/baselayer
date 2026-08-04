"""
Pack Studio - Marketplace Listing Copy

Formats the already-generated listing into ready-to-paste listings for other
marketplaces, respecting each platform's known field limits. This does not
call any marketplace API -- Gumroad is the only platform pack_studio can
publish to directly (see publishers.py, real and opt-in); everything here is
copy you paste into that platform's own listing form. These platforms either
require an approved developer app (Etsy, Shopify), have no verified write
API for product creation, or can't be tested against a live account here --
guessing at API calls for them risks silently corrupting a real store, so
this stays copy-paste by design.
"""

import re
from typing import Any, Dict, List

from .brief import ProductBrief


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _derive_tags(product_brief: ProductBrief, max_tags: int, max_len: int) -> List[str]:
    if product_brief.keywords:
        return [k.strip()[:max_len] for k in product_brief.keywords][:max_tags]
    words = re.findall(
        r"[A-Za-z][A-Za-z\-]+",
        f"{product_brief.title} {product_brief.audience} {product_brief.product_type.replace('_', ' ')}",
    )
    stop = {"the", "a", "an", "and", "or", "for", "to", "of", "with", "your", "you"}
    tags: List[str] = []
    for word in words:
        w = word.lower()
        if w in stop or len(w) < 3 or w in tags:
            continue
        tags.append(w[:max_len])
        if len(tags) >= max_tags:
            break
    return tags


def etsy_listing(product_brief: ProductBrief, listing_data: Dict[str, Any]) -> str:
    title = _truncate(listing_data.get("title", product_brief.title), 140)
    tags = _derive_tags(product_brief, max_tags=13, max_len=20)
    lines = [
        f"Title ({len(title)}/140 chars): {title}",
        "",
        f"Price: {product_brief.price_display}",
        "",
        "Description:",
        listing_data.get("description", ""),
        "",
        f"Tags (max 13, max 20 chars each): {', '.join(tags)}",
        "",
        "Category: Craft Supplies & Tools > Digital > Digital Prints & Downloads (adjust to the closest fit)",
    ]
    return "\n".join(lines)


def shopify_listing(product_brief: ProductBrief, listing_data: Dict[str, Any]) -> str:
    seo_title = _truncate(listing_data.get("title", product_brief.title), 70)
    meta_description = _truncate(
        listing_data.get("subtitle", "") or listing_data.get("description", ""), 160
    )
    lines = [
        f"Product title: {listing_data.get('title', product_brief.title)}",
        f"SEO title ({len(seo_title)}/70 chars): {seo_title}",
        f"Meta description ({len(meta_description)}/160 chars): {meta_description}",
        "",
        f"Price: {product_brief.price_display}",
        "",
        "Product description (HTML/rich text field):",
        listing_data.get("description", ""),
        "",
        "Note: requires a digital-downloads app (e.g. Shopify's own Digital Downloads) to deliver the file.",
    ]
    return "\n".join(lines)


def payhip_listing(product_brief: ProductBrief, listing_data: Dict[str, Any]) -> str:
    lines = [
        f"Product name: {listing_data.get('title', product_brief.title)}",
        f"Price: {product_brief.price_display}",
        "",
        "Description:",
        listing_data.get("description", ""),
        "",
        "Features:",
        *[f"- {f}" for f in listing_data.get("features", [])],
    ]
    return "\n".join(lines)


def lemonsqueezy_listing(product_brief: ProductBrief, listing_data: Dict[str, Any]) -> str:
    lines = [
        f"Product name: {listing_data.get('title', product_brief.title)}",
        f"Price: {product_brief.price_display}",
        "",
        "Description (supports basic HTML):",
        listing_data.get("description", ""),
    ]
    return "\n".join(lines)


def podia_listing(product_brief: ProductBrief, listing_data: Dict[str, Any]) -> str:
    lines = [
        f"Product title: {listing_data.get('title', product_brief.title)}",
        f"Price: {product_brief.price_display}",
        "",
        "Sales page copy:",
        listing_data.get("subtitle", ""),
        "",
        listing_data.get("description", ""),
        "",
        "What's included:",
        *[f"- {f}" for f in listing_data.get("features", [])],
    ]
    return "\n".join(lines)


def teachable_listing(product_brief: ProductBrief, listing_data: Dict[str, Any]) -> str:
    lines = [
        "Note: Teachable is built for courses -- position this as a short mini-course/masterclass.",
        f"Course title: {listing_data.get('title', product_brief.title)}",
        f"Course subtitle: {listing_data.get('subtitle', '')}",
        f"Price: {product_brief.price_display}",
        "",
        "Course description:",
        listing_data.get("description", ""),
        "",
        "What students will learn:",
        *[f"- {b}" for b in listing_data.get("benefits", [])],
    ]
    return "\n".join(lines)


def sellfy_listing(product_brief: ProductBrief, listing_data: Dict[str, Any]) -> str:
    title = _truncate(listing_data.get("title", product_brief.title), 100)
    lines = [
        f"Title ({len(title)}/100 chars): {title}",
        f"Price: {product_brief.price_display}",
        "",
        "Description:",
        listing_data.get("description", ""),
    ]
    return "\n".join(lines)


def kdp_listing(product_brief: ProductBrief, listing_data: Dict[str, Any]) -> str:
    lines: List[str] = []
    if product_brief.product_type not in ("pdf_guide", "prompt_library", "cheat_sheet"):
        lines.append(
            "Note: KDP is built for books -- this product type isn't a natural fit, but here's a "
            "best-effort listing.\n"
        )
    title = _truncate(listing_data.get("title", product_brief.title), 200)
    lines += [
        f"Book title: {title}",
        f"Subtitle: {listing_data.get('subtitle', '')}",
        f"Price: {product_brief.price_display} (KDP takes a royalty share -- check current rates)",
        "",
        "Book description (KDP allows limited HTML: <b>, <i>, <br>, <ul><li>):",
        listing_data.get("description", ""),
        "",
        "7 keywords (KDP allows up to 7, comma-separated):",
        ", ".join(_derive_tags(product_brief, max_tags=7, max_len=25)),
        "",
        "Categories: choose 2 from KDP's category list closest to this topic.",
    ]
    return "\n".join(lines)


def render_marketplace_markdown(product_brief: ProductBrief, listing_data: Dict[str, Any]) -> str:
    sections = [
        ("Etsy", etsy_listing(product_brief, listing_data)),
        ("Shopify", shopify_listing(product_brief, listing_data)),
        ("Payhip", payhip_listing(product_brief, listing_data)),
        ("Lemon Squeezy", lemonsqueezy_listing(product_brief, listing_data)),
        ("Podia", podia_listing(product_brief, listing_data)),
        ("Teachable", teachable_listing(product_brief, listing_data)),
        ("Sellfy", sellfy_listing(product_brief, listing_data)),
        ("Amazon KDP", kdp_listing(product_brief, listing_data)),
    ]
    parts = [
        "# Marketplace Listings",
        "",
        "Copy-paste-ready listings for each platform, formatted to that platform's known field "
        "limits. Gumroad can be published for you automatically (`--publish` with "
        "GUMROAD_ACCESS_TOKEN set) -- everything below is manual-paste, since none of these have "
        "verified live write APIs to build against safely (see the note at the top of "
        "marketplace_copy.py).",
        "",
    ]
    for label, content in sections:
        parts.append(f"## {label}")
        parts.append("")
        parts.append(content)
        parts.append("")
    return "\n".join(parts)
