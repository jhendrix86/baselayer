"""
Pack Studio - Renderer

Turns generated sections into real files: markdown, plain text, a real PDF
(not a placeholder), a real cover image, and a real ZIP bundle.
"""

import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

# Tried in order; the first pair that exists on disk wins. Covers Windows,
# common Linux font packages, and macOS. If none exist, PDF/cover generation
# falls back to core fonts and ASCII-safe text instead of crashing on the
# em-dashes/curly-quotes/bullets that LLM output routinely contains.
_FONT_CANDIDATES: List[Tuple[str, str]] = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
]

_UNICODE_ASCII_MAP = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "--", "\u2026": "...", "\u2022": "*",
    "\u00a0": " ",
}


def _find_font_pair() -> Optional[Tuple[str, str]]:
    for regular, bold in _FONT_CANDIDATES:
        if Path(regular).exists() and Path(bold).exists():
            return regular, bold
    return None


def _ascii_safe(text: str) -> str:
    """Best-effort transliteration for when no Unicode TTF font is available.
    Common typographic characters are mapped to ASCII equivalents; anything
    else outside Latin-1 is replaced with '?' rather than crashing fpdf2."""
    for uni, ascii_eq in _UNICODE_ASCII_MAP.items():
        text = text.replace(uni, ascii_eq)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _mc(pdf: FPDF, h: float, text: str, ascii_only: bool = False) -> None:
    """multi_cell wrapper that always resets x to the left margin first.

    fpdf2's multi_cell leaves the cursor at the right edge of the block by
    default, so a full-width (w=0) call right after another computes almost
    no remaining width and raises "Not enough horizontal space".
    """
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, h, _ascii_safe(text) if ascii_only else text)


def sanitize_filename(name: str) -> str:
    sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
    sanitized = re.sub(r'\s+', '_', sanitized)
    return sanitized.strip('. ') or "product"


def build_markdown(title: str, sections: Dict[str, str], structure: List[Dict[str, Any]]) -> str:
    parts = [f"# {title}", ""]
    for section in structure:
        parts.append(f"## {section['title']}")
        parts.append("")
        parts.append(sections.get(section["name"], ""))
        parts.append("")
    return "\n".join(parts)


def build_text(title: str, sections: Dict[str, str], structure: List[Dict[str, Any]]) -> str:
    parts = [title, "=" * len(title), ""]
    for section in structure:
        parts.append(section["title"].upper())
        parts.append("-" * len(section["title"]))
        parts.append("")
        body = sections.get(section["name"], "")
        body = re.sub(r'\*\*(.+?)\*\*', r'\1', body)
        body = re.sub(r'^#+\s*', '', body, flags=re.MULTILINE)
        parts.append(body)
        parts.append("")
    return "\n".join(parts)


def _register_font(pdf: FPDF) -> Tuple[str, bool]:
    """Register a Unicode-capable font if one is found on disk.

    Returns (font_family, ascii_only). ascii_only is True when we had to
    fall back to a core PDF font, so callers know to transliterate text
    instead of risking an encoding crash.
    """
    pair = _find_font_pair()
    if pair:
        try:
            pdf.add_font("Body", "", pair[0])
            pdf.add_font("Body", "B", pair[1])
            return "Body", False
        except Exception:
            pass
    return "helvetica", True


def _pdf_write_markdown_block(pdf: FPDF, font_family: str, text: str, ascii_only: bool) -> None:
    """Minimal markdown-aware renderer: headings, bullets, numbered lists, fenced code."""
    in_code = False
    for raw_line in text.split("\n"):
        line = raw_line.rstrip()

        if line.strip().startswith("```"):
            in_code = not in_code
            continue

        if in_code:
            pdf.set_font(font_family, "", 10)
            _mc(pdf, 5.5, "    " + line, ascii_only)
            continue

        if not line.strip():
            pdf.ln(2)
            continue

        # Setext-style heading underlines ("Title\n===" or "Title\n---") are
        # purely decorative once the previous line was already rendered.
        if re.match(r'^(=+|-{3,})$', line.strip()):
            continue

        heading_match = re.match(r'^(#{1,4})\s+(.*)', line)
        if heading_match:
            level = len(heading_match.group(1))
            size = {1: 16, 2: 14, 3: 12, 4: 11}.get(level, 11)
            pdf.set_font(font_family, "B", size)
            _mc(pdf, 7, heading_match.group(2), ascii_only)
            pdf.ln(1)
            continue

        bullet_match = re.match(r'^\s*[-*]\s+(.*)', line)
        if bullet_match:
            pdf.set_font(font_family, "", 11)
            _mc(pdf, 6, f"  \u2022 {bullet_match.group(1)}", ascii_only)
            continue

        numbered_match = re.match(r'^\s*(\d+)[.)]\s+(.*)', line)
        if numbered_match:
            pdf.set_font(font_family, "", 11)
            _mc(pdf, 6, f"  {numbered_match.group(1)}. {numbered_match.group(2)}", ascii_only)
            continue

        clean = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
        clean = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'\1', clean)
        pdf.set_font(font_family, "", 11)
        _mc(pdf, 6, clean, ascii_only)


def build_pdf(title: str, sections: Dict[str, str], structure: List[Dict[str, Any]], out_path: Path) -> None:
    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(20, 20, 20)
    font_family, ascii_only = _register_font(pdf)

    pdf.add_page()
    pdf.set_font(font_family, "B", 24)
    _mc(pdf, 12, title, ascii_only)
    pdf.ln(6)

    for section in structure:
        pdf.set_font(font_family, "B", 15)
        _mc(pdf, 9, section["title"], ascii_only)
        pdf.ln(2)
        _pdf_write_markdown_block(pdf, font_family, sections.get(section["name"], ""), ascii_only)
        pdf.ln(4)

    pdf.output(str(out_path))


def _load_font(path: Optional[str], size: int) -> ImageFont.FreeTypeFont:
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    try:
        # Pillow >=10.1 supports a scalable default font via size=; older
        # Pillow's load_default() takes no arguments and returns a tiny
        # fixed-size bitmap font instead.
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _wrap_text(draw: "ImageDraw.ImageDraw", text: str, font, max_width: int) -> List[str]:
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def build_cover_image(
    title: str,
    subtitle: str,
    out_path: Path,
    width: int = 1200,
    height: int = 630,
    bg_color: str = "#14213d",
    accent_color: str = "#fca311",
    text_color: str = "#ffffff",
) -> None:
    pair = _find_font_pair()
    regular_path, bold_path = pair if pair else (None, None)

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    title_font = _load_font(bold_path, 62)
    subtitle_font = _load_font(regular_path, 28)

    if pair is None:
        # No TTF found: PIL's bitmap default font can't render most Unicode
        # punctuation either, so transliterate the same way the PDF path does.
        title = _ascii_safe(title)
        subtitle = _ascii_safe(subtitle)

    margin = 80
    max_width = width - 2 * margin

    title_lines = _wrap_text(draw, title, title_font, max_width)[:4]
    subtitle_lines = _wrap_text(draw, subtitle, subtitle_font, max_width)[:2]

    line_height = 74
    sub_line_height = 40
    block_height = len(title_lines) * line_height + 20 + len(subtitle_lines) * sub_line_height
    y = max((height - block_height) // 2, margin)

    draw.rectangle([margin, y - 30, margin + 90, y - 22], fill=accent_color)

    for line in title_lines:
        draw.text((margin, y), line, font=title_font, fill=text_color)
        y += line_height

    y += 10
    for line in subtitle_lines:
        draw.text((margin, y), line, font=subtitle_font, fill=accent_color)
        y += sub_line_height

    img.save(out_path)


def build_zip(files: Dict[str, Path], out_path: Path) -> None:
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, path in files.items():
            zf.write(path, arcname=arcname)
