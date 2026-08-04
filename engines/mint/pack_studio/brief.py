"""
Pack Studio - Product Brief

A single structured brief holds everything pack_studio needs to generate a
full pack and its marketing: not just the topic, but the details that make
the output specific and usable instead of generic (real link for CTAs,
brand name, tone, SEO keywords, points that must be covered).
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ProductBrief:
    title: str
    brief: str
    product_type: str = "pdf_guide"
    audience: str = "general"
    price_cents: int = 900
    tone: str = "professional but approachable"
    keywords: List[str] = field(default_factory=list)
    key_points: List[str] = field(default_factory=list)
    link: Optional[str] = None
    brand: Optional[str] = None

    @property
    def price_display(self) -> str:
        return f"${self.price_cents / 100:.2f}"

    def context_block(self) -> str:
        """Common context lines injected into every generation prompt."""
        lines = [
            f"Product title: {self.title}",
            f"Product type: {self.product_type}",
            f"Target audience: {self.audience}",
            f"Price: {self.price_display}",
            f"Tone/voice to write in: {self.tone}",
        ]
        if self.brand:
            lines.append(f"Brand/creator name: {self.brand}")
        if self.keywords:
            lines.append(f"SEO keywords to weave in naturally where relevant: {', '.join(self.keywords)}")
        if self.key_points:
            lines.append("Must cover these specific points somewhere in the pack:")
            lines.extend(f"- {p}" for p in self.key_points)
        return "\n".join(lines)

    def apply_link(self, text: str) -> str:
        """Fill in the real product link, or leave the placeholder with a note if none was given."""
        if self.link:
            return text.replace("[LINK]", self.link)
        return text
