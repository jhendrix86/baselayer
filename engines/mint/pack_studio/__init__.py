"""
MINT Pack Studio

Standalone, dependency-light pipeline that turns a short brief into a
sellable digital product pack (PDF + markdown + text + cover image + ZIP,
plus Gumroad-style listing copy). Uses a local Ollama model for content
generation, so it needs nothing beyond what's already installed.

Entry point: `python -m engines.mint.pack_studio.cli --brief "..." --title "..."`
"""
