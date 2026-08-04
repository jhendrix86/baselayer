"""
Pack Studio - CLI

Turns a brief into a complete, sellable digital product pack, plus
ready-to-use listing copy for other marketplaces and a social/email
marketing kit.

Example:
    python -m engines.mint.pack_studio.cli \\
        --title "The 10-Minute Morning Routine" \\
        --brief "A guide teaching busy professionals a simple 10-minute morning routine that improves focus and energy" \\
        --type pdf_guide --audience "busy professionals" --price 12 \\
        --link "https://example.gumroad.com/l/morning-routine" --brand "Acme Guides" \\
        --tone "warm and encouraging, no jargon" \\
        --keywords "morning routine, focus, productivity" \\
        --key-points "no equipment needed, works for shift workers too"

For a longer brief, write it in a file and pass --brief-file instead of (or
in addition to) --brief. If a run is interrupted partway through, rerunning
the exact same command resumes from the last completed step instead of
starting over -- pass --fresh to force a clean regenerate instead.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from . import content, listing, marketing, marketplace_copy, render
from .brief import ProductBrief
from .progress import Progress

DEFAULT_OUTPUT_ROOT = Path("~/mint_packs").expanduser()


def _build_gumroad_payload(listing_data: Dict[str, Any], price_cents: int) -> Dict[str, Any]:
    return {
        "name": listing_data.get("title", ""),
        "description": listing_data.get("description", ""),
        "price": price_cents,
    }


def publish_to_gumroad(listing_data: Dict[str, Any], price_cents: int, dry_run: bool = False) -> None:
    """Publish to Gumroad. Product creation via POST /v2/products is
    confirmed working against a live account (verified 2026-08-04, returned
    a real product short_url). What's still unconfirmed: whether the
    created product is published or draft by default, and how/whether the
    downloadable file can be attached via the API -- this call never
    attaches one, so always check the result on Gumroad's dashboard and
    attach the file manually."""
    payload = _build_gumroad_payload(listing_data, price_cents)

    if dry_run:
        print("\n--- Gumroad dry run: nothing was sent ---")
        print(json.dumps(payload, indent=2))
        print(
            "This will create a real, live product on your Gumroad account when run without "
            "--dry-run-publish (confirmed working). It will NOT upload the product file -- "
            "attach it manually via the Gumroad dashboard afterward.\n"
        )
        return

    token = os.getenv("GUMROAD_ACCESS_TOKEN")
    if not token:
        print("Skipping Gumroad publish: GUMROAD_ACCESS_TOKEN is not set.")
        return

    try:
        resp = httpx.post(
            "https://api.gumroad.com/v2/products",
            headers={"Authorization": f"Bearer {token}"},
            data=payload,
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
    except httpx.HTTPStatusError as e:
        print(f"Gumroad publish failed ({e.response.status_code}): {e.response.text[:300]}", file=sys.stderr)
        return
    except Exception as e:
        print(f"Gumroad publish failed: {e}", file=sys.stderr)
        return

    product = result.get("product") or {}
    if product:
        print(f"Published to Gumroad: {product.get('short_url', product)}")
    else:
        print(f"Gumroad responded without a product object -- check manually: {result}")
    print(
        "IMPORTANT: check this listing on your Gumroad dashboard now -- confirm whether it's "
        "published or draft, and attach product.pdf / the ZIP manually. The file is never "
        "uploaded automatically."
    )


def build_pack(
    product_brief: ProductBrief,
    model: str,
    output_dir: Path,
    publish: bool = False,
    dry_run_publish: bool = False,
    include_marketing: bool = True,
    include_marketplace_copy: bool = True,
    fresh: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    progress = Progress(output_dir, product_brief, fresh=fresh)
    if progress.resumed:
        print("Found a partial run for this exact brief -- resuming, skipping completed steps.\n")

    steps = ["Generate content", "Render PDF/cover/text", "Generate listing copy"]
    if include_marketing:
        steps.append("Generate marketing kit")
    if include_marketplace_copy:
        steps.append("Generate marketplace listings")
    steps.append("Package ZIP")
    total = len(steps)
    step_num = 0

    def announce(label: str) -> None:
        nonlocal step_num
        step_num += 1
        print(f"[{step_num}/{total}] {label}...")

    def on_section_done(section: Dict[str, Any], text: str) -> None:
        print(f"      done: {section['title']}")
        progress.save_section(section["name"], text)

    announce(steps[0])
    structure = content.get_structure(product_brief.product_type)
    sections = content.generate_product(
        product_brief, model=model,
        on_section_done=on_section_done,
        existing_sections=progress.sections(),
    )

    announce(steps[1])
    slug = render.sanitize_filename(product_brief.title)
    md_path = output_dir / "product.md"
    txt_path = output_dir / "product.txt"
    pdf_path = output_dir / "product.pdf"
    cover_path = output_dir / "cover.png"

    md_path.write_text(render.build_markdown(product_brief.title, sections, structure), encoding="utf-8")
    txt_path.write_text(render.build_text(product_brief.title, sections, structure), encoding="utf-8")
    render.build_pdf(product_brief.title, sections, structure, pdf_path)
    render.build_cover_image(product_brief.title, product_brief.audience, cover_path)

    announce(steps[2])
    content_summary = "\n\n".join(sections.values())
    cached_listing = progress.listing_data()
    if cached_listing is not None:
        print("      resuming: listing copy already generated")
        listing_data = cached_listing
    else:
        listing_data = listing.generate_listing_copy(product_brief, content_summary, model=model)
        progress.save_listing(listing_data)
    listing_path = output_dir / "listing_copy.md"
    listing_path.write_text(listing.render_listing_markdown(listing_data), encoding="utf-8")

    created_files = [pdf_path.name, md_path.name, txt_path.name, cover_path.name, listing_path.name]

    if include_marketing:
        announce(steps[3])

        def on_platform_done(key: str, text: str) -> None:
            print(f"      done: {marketing.PLATFORM_SPECS[key]['label']}")
            progress.save_marketing_platform(key, text)

        marketing_kit = marketing.generate_marketing_kit(
            product_brief, listing_data, model=model,
            on_platform_done=on_platform_done,
            existing_kit=progress.marketing_kit(),
        )
        marketing_path = output_dir / "marketing_kit.md"
        marketing_path.write_text(marketing.render_marketing_markdown(marketing_kit), encoding="utf-8")
        created_files.append(marketing_path.name)

    if include_marketplace_copy:
        announce(steps[3 + int(include_marketing)])
        marketplace_path = output_dir / "marketplace_listings.md"
        marketplace_path.write_text(
            marketplace_copy.render_marketplace_markdown(product_brief, listing_data), encoding="utf-8"
        )
        created_files.append(marketplace_path.name)

    announce(steps[-1])
    # Only the actual product files go in the ZIP customers receive -- listing
    # copy and marketing materials are for the creator, not the buyer.
    zip_path = output_dir / f"{slug}.zip"
    render.build_zip(
        {
            pdf_path.name: pdf_path,
            md_path.name: md_path,
            txt_path.name: txt_path,
            cover_path.name: cover_path,
        },
        zip_path,
    )
    created_files.append(zip_path.name)

    manifest = {
        "title": product_brief.title,
        "product_type": product_brief.product_type,
        "audience": product_brief.audience,
        "price_cents": product_brief.price_cents,
        "tone": product_brief.tone,
        "keywords": product_brief.keywords,
        "key_points": product_brief.key_points,
        "link": product_brief.link,
        "brand": product_brief.brand,
        "model": model,
        "word_count": sum(len(s.split()) for s in sections.values()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": created_files,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if publish or dry_run_publish:
        publish_to_gumroad(listing_data, product_brief.price_cents, dry_run=dry_run_publish)

    # Everything succeeded -- the checkpoint is no longer needed. Keeping it
    # around would let a *different* future run with a colliding hash resume
    # from stale data instead of generating fresh content.
    progress.clear()

    return zip_path


def _split_list(raw: str) -> List[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _resolve_brief_text(brief: Optional[str], brief_file: Optional[str]) -> str:
    parts = []
    if brief:
        parts.append(brief.strip())
    if brief_file:
        parts.append(Path(brief_file).expanduser().read_text(encoding="utf-8").strip())
    return "\n\n".join(parts)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a sellable digital product pack from a brief.")
    parser.add_argument("--title", required=True, help="Product title")
    parser.add_argument("--brief", default=None, help="What the product should teach/cover")
    parser.add_argument("--brief-file", default=None, help="Path to a text/markdown file with a longer brief (combined with --brief if both given)")
    parser.add_argument("--type", default="pdf_guide", choices=sorted(content.PRODUCT_STRUCTURES), dest="product_type")
    parser.add_argument("--audience", default="general", help="Target audience")
    parser.add_argument("--price", type=float, default=9.0, help="Price in dollars")
    parser.add_argument("--tone", default="professional but approachable", help="Voice/tone for all generated copy")
    parser.add_argument("--keywords", default="", help="Comma-separated SEO keywords to weave in and use as marketplace tags")
    parser.add_argument("--key-points", default="", help="Comma-separated points the content must specifically cover")
    parser.add_argument("--link", default=None, help="Real product URL to use in CTAs and marketing copy (a [LINK] placeholder is left otherwise)")
    parser.add_argument("--brand", default=None, help="Creator/brand name to reference in generated copy")
    parser.add_argument("--model", default=content.DEFAULT_MODEL)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--publish", action="store_true", help="Also publish to Gumroad (requires GUMROAD_ACCESS_TOKEN); best-effort/unverified, see publish_to_gumroad docstring")
    parser.add_argument("--dry-run-publish", action="store_true", help="Print the Gumroad payload that would be sent, without sending it or requiring a token")
    parser.add_argument("--no-marketing", action="store_true", help="Skip generating the social/email marketing kit")
    parser.add_argument("--no-marketplace-copy", action="store_true", help="Skip generating other marketplaces' listing copy")
    parser.add_argument("--fresh", action="store_true", help="Ignore any saved progress from a previous interrupted run and start clean")
    args = parser.parse_args(argv)

    brief_text = _resolve_brief_text(args.brief, args.brief_file)
    if not brief_text:
        parser.error("provide --brief and/or --brief-file")

    if args.price < 0:
        parser.error("--price cannot be negative")

    try:
        model, model_warning = content.check_ollama_and_resolve_model(args.model)
    except content.OllamaUnavailableError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if model_warning:
        print(f"Warning: {model_warning}")

    output_dir = (
        Path(args.output_dir).expanduser()
        if args.output_dir
        else DEFAULT_OUTPUT_ROOT / render.sanitize_filename(args.title)
    )

    product_brief = ProductBrief(
        title=args.title,
        brief=brief_text,
        product_type=args.product_type,
        audience=args.audience,
        price_cents=int(round(args.price * 100)),
        tone=args.tone,
        keywords=_split_list(args.keywords),
        key_points=_split_list(args.key_points),
        link=args.link,
        brand=args.brand,
    )

    try:
        zip_path = build_pack(
            product_brief,
            model=model,
            output_dir=output_dir,
            publish=args.publish,
            dry_run_publish=args.dry_run_publish,
            include_marketing=not args.no_marketing,
            include_marketplace_copy=not args.no_marketplace_copy,
            fresh=args.fresh,
        )
    except Exception as e:
        print(f"\nError: pack generation failed: {e}", file=sys.stderr)
        print(
            f"Progress up to this point is saved in {output_dir} -- rerun the same command "
            "to resume instead of starting over.",
            file=sys.stderr,
        )
        return 1

    print(f"\nDone. Pack folder: {output_dir}")
    print(f"Sellable ZIP (customer files only): {zip_path}")
    print("Creator files (not in the ZIP): listing_copy.md, marketplace_listings.md, marketing_kit.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
