"""
Pack Studio - Marketing Kit Generator

Generates platform-tailored, ready-to-post marketing copy for the product
pack: social media posts, a short-form video script, and an email blast.
This produces copy for a human to review and post -- it never posts
anything itself.
"""

import re
from typing import Any, Callable, Dict, Optional

from .brief import ProductBrief
from .content import chat

_PREAMBLE_RE = re.compile(r"^(here'?s|here is|sure,?|certainly,?)\b.{0,80}:\s*$", re.IGNORECASE)


def _strip_preamble(text: str) -> str:
    """Small local models sometimes prefix their answer with 'Here's the X:'
    despite being told to output only the content -- drop that line if present."""
    lines = text.split("\n", 1)
    if lines and _PREAMBLE_RE.match(lines[0].strip()):
        return lines[1].lstrip("\n") if len(lines) > 1 else ""
    return text

PLATFORM_SPECS: Dict[str, Dict[str, str]] = {
    "twitter_thread": {
        "label": "X / Twitter Thread",
        "system": (
            "You write viral, benefit-driven Twitter/X threads promoting digital products. "
            "Write a 5-tweet thread. Each tweet must be under 280 characters, numbered (1/5 etc.), "
            "on its own line, separated by a blank line. Tweet 1 is a scroll-stopping hook. "
            "Tweet 5 ends with a clear call to action and a '[LINK]' placeholder for the product URL. "
            "No hashtags in the middle tweets; at most 2 relevant hashtags in the final tweet."
        ),
    },
    "instagram_caption": {
        "label": "Instagram Caption",
        "system": (
            "You write Instagram captions for digital products. Write an engaging caption with "
            "short punchy lines and line breaks, ending with a call to action and 'Link in bio'. "
            "After the caption, add a blank line then 15-20 relevant hashtags separated by spaces, "
            "mixing broad and niche tags."
        ),
    },
    "tiktok_script": {
        "label": "TikTok / Reels Script",
        "system": (
            "You write 30-45 second short-form video scripts (TikTok/Instagram Reels/YouTube "
            "Shorts) that sell digital products without feeling like an ad. Structure: HOOK (first "
            "2 seconds, must stop the scroll), BODY (deliver one genuinely useful tip from the "
            "product), CTA (soft pitch for the full product). Label each section. Include "
            "suggested on-screen text in [brackets]."
        ),
    },
    "pinterest_pin": {
        "label": "Pinterest Pin",
        "system": (
            "You write Pinterest pin copy for digital products. Respond in this exact format:\n"
            "Pin Title: <max 100 characters, keyword-rich>\n"
            "Pin Description: <max 500 characters, benefit-driven, include 2-3 relevant keywords "
            "naturally>\n"
            "Suggested Board: <a realistic Pinterest board name this would fit on>"
        ),
    },
    "linkedin_post": {
        "label": "LinkedIn Post",
        "system": (
            "You write professional LinkedIn posts promoting digital products to a business "
            "audience. Tone: credible, value-first, not salesy. 3-5 short paragraphs, use line "
            "breaks between them, end with a call to action. Include 3-5 relevant hashtags on "
            "their own line at the end."
        ),
    },
    "facebook_post": {
        "label": "Facebook Post",
        "system": (
            "You write casual, engaging Facebook posts for digital products. Start with a "
            "relatable question or statement, keep it conversational, end with a call to action. "
            "Include at most 2 hashtags."
        ),
    },
    "reddit_post": {
        "label": "Reddit Post (value-first)",
        "system": (
            "You write Reddit posts that share genuinely useful advice or a personal-style story "
            "related to the product's topic, written in Reddit's casual, non-promotional voice. "
            "Reddit communities downvote and remove hard sales posts, so the post must read as "
            "authentic value first, with only a brief, low-key mention of the resource near the "
            "end -- never a headline pitch. Respond in this format:\n"
            "Suggested Subreddit: <a realistic subreddit name for this topic>\n"
            "Title: <a natural, non-clickbait Reddit post title>\n"
            "Body: <the post body>"
        ),
    },
    "youtube_description": {
        "label": "YouTube Video Description",
        "system": (
            "You write YouTube video descriptions for a video promoting a digital product. "
            "Structure: a 2-3 sentence hook/summary, then a blank line, then '[LINK] Get it here', "
            "then a blank line, then a 'Timestamps' section with a placeholder '00:00 Intro', then "
            "a blank line, then 8-10 relevant hashtags."
        ),
    },
    "email_blast": {
        "label": "Email Marketing Blast",
        "system": (
            "You write marketing emails for a creator's list, announcing a new digital product. "
            "Respond in this exact format:\n"
            "Subject: <compelling subject line, under 60 characters>\n"
            "Preheader: <preview text, under 100 characters>\n"
            "Body:\n<the full email body, warm and personal tone, 150-300 words, with a clear CTA "
            "button text on its own line at the end formatted as [CTA: button text]>"
        ),
    },
}


def generate_marketing_kit(
    product_brief: ProductBrief,
    listing_data: Dict[str, Any],
    model: str,
    on_platform_done: Optional[Callable[[str, str], None]] = None,
    existing_kit: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Generate ready-to-post marketing copy for every supported platform.

    existing_kit lets a caller resume a crashed run: platforms already
    present are reused as-is, so only the missing ones cost a fresh call.
    """
    summary = listing_data.get("description", "") or ""
    features = ", ".join(listing_data.get("features", []) or [])

    kit: Dict[str, str] = dict(existing_kit or {})
    for key, spec in PLATFORM_SPECS.items():
        if key in kit:
            continue
        user_prompt = (
            f"{product_brief.context_block()}\n"
            f"Product summary: {summary[:600]}\n"
            f"Key features: {features}\n\n"
            "Write the marketing copy described in the system prompt for this specific product. "
            "Use the literal placeholder [LINK] anywhere a product URL belongs -- never invent one."
        )
        messages = [
            {"role": "system", "content": spec["system"]},
            {"role": "user", "content": user_prompt},
        ]
        raw = chat(messages, model=model, temperature=0.85, max_tokens=700)
        kit[key] = product_brief.apply_link(_strip_preamble(raw))
        if on_platform_done:
            on_platform_done(key, kit[key])
    return kit


def render_marketing_markdown(kit: Dict[str, str]) -> str:
    parts = [
        "# Marketing Kit",
        "",
        "Ready-to-post copy for each platform. Review before posting -- nothing here is posted "
        "automatically.",
        "",
    ]
    for key, spec in PLATFORM_SPECS.items():
        if key not in kit:
            continue
        parts.append(f"## {spec['label']}")
        parts.append("")
        parts.append(kit[key])
        parts.append("")
    return "\n".join(parts)
