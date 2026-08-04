"""
Pack Studio - Content Generator

Expands a brief into structured section content using a local Ollama model.
"""

import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from .brief import ProductBrief

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2:latest"

# Section structure per product type: (name, title, description, target_word_count)
PRODUCT_STRUCTURES: Dict[str, List[Dict[str, Any]]] = {
    "pdf_guide": [
        {"name": "introduction", "title": "Introduction", "description": "Hook the reader and state the problem", "words": 300},
        {"name": "problem_statement", "title": "The Problem", "description": "Clearly define the problem and its impact", "words": 400},
        {"name": "solution_overview", "title": "Solution Overview", "description": "Present the main solution and approach", "words": 600},
        {"name": "implementation_steps", "title": "Step-by-Step Implementation", "description": "Detailed, actionable implementation steps", "words": 800},
        {"name": "examples", "title": "Examples", "description": "Concrete, realistic examples applying the solution", "words": 400},
        {"name": "conclusion", "title": "Conclusion", "description": "Summarize key takeaways and next steps", "words": 200},
    ],
    "template_pack": [
        {"name": "overview", "title": "Overview", "description": "Introduce what this template pack covers", "words": 200},
        {"name": "templates", "title": "Templates", "description": "A collection of concrete, ready-to-use templates with real example content, clearly separated", "words": 1000},
        {"name": "usage_guide", "title": "Usage Guide", "description": "How to adapt and use each template effectively", "words": 600},
        {"name": "best_practices", "title": "Best Practices", "description": "Tips for getting the most value out of the templates", "words": 400},
    ],
    "checklist": [
        {"name": "introduction", "title": "Introduction", "description": "Purpose and scope of the checklist", "words": 150},
        {"name": "checklist_items", "title": "The Checklist", "description": "A comprehensive, numbered checklist with brief explanations for each item", "words": 800},
        {"name": "instructions", "title": "How to Use This Checklist", "description": "Practical instructions for applying the checklist", "words": 400},
    ],
    "cheat_sheet": [
        {"name": "overview", "title": "Overview", "description": "What this cheat sheet covers and who it's for", "words": 150},
        {"name": "quick_reference", "title": "Quick Reference", "description": "Dense, scannable reference content (tables, short entries, key facts)", "words": 700},
        {"name": "tips_and_tricks", "title": "Tips & Tricks", "description": "Extra shortcuts and lesser-known tips", "words": 350},
    ],
    "prompt_library": [
        {"name": "introduction", "title": "Introduction", "description": "What this prompt library is for and how it's organized", "words": 200},
        {"name": "prompt_categories", "title": "Prompts", "description": "Concrete, ready-to-use prompts grouped by category, each with a short usage note", "words": 900},
        {"name": "usage_instructions", "title": "How to Use These Prompts", "description": "General guidance for adapting prompts effectively", "words": 300},
        {"name": "customization_tips", "title": "Customization Tips", "description": "How to tweak prompts for different tools and use cases", "words": 300},
    ],
    "code_snippets": [
        {"name": "overview", "title": "Overview", "description": "What this snippet collection covers and the target language/stack", "words": 200},
        {"name": "snippets", "title": "Snippets", "description": "Concrete, working code snippets in fenced code blocks with a short explanation before each", "words": 900},
        {"name": "usage_notes", "title": "Usage Notes", "description": "Setup, dependencies, and integration notes", "words": 400},
        {"name": "best_practices", "title": "Best Practices", "description": "Tips for using these snippets safely and effectively", "words": 300},
    ],
    "notion_template": [
        {"name": "overview", "title": "Overview", "description": "What this Notion template is for and who it helps", "words": 200},
        {"name": "template_structure", "title": "Template Structure", "description": "The pages, databases, and properties that make up the template, described concretely", "words": 700},
        {"name": "setup_instructions", "title": "Setup Instructions", "description": "Step-by-step instructions to recreate/import the template in Notion", "words": 500},
        {"name": "customization_guide", "title": "Customization Guide", "description": "How to adapt the template to different workflows", "words": 300},
    ],
}

SYSTEM_PROMPT = (
    "You are a professional digital-product writer. Write complete, polished, "
    "ready-to-sell content for a paid digital product. Rules: never use placeholder "
    "text like [TODO] or 'coming soon'; never write in the first person about "
    "yourself; never mention that you are an AI or that this content was generated; "
    "no meta-commentary about the writing task itself. Output only the requested "
    "section content, formatted in markdown, with no top-level heading (the caller "
    "adds headings)."
)


class OllamaUnavailableError(RuntimeError):
    pass


def get_structure(product_type: str) -> List[Dict[str, Any]]:
    return PRODUCT_STRUCTURES.get(product_type, PRODUCT_STRUCTURES["pdf_guide"])


def check_ollama_and_resolve_model(preferred_model: str = DEFAULT_MODEL) -> Tuple[str, Optional[str]]:
    """Confirm Ollama is reachable and return (model_to_use, warning_or_None).

    The warning is set when the preferred model isn't pulled and a
    substitute was picked, so the caller can tell the user rather than
    silently generating with a different model than they asked for.
    """
    try:
        resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        resp.raise_for_status()
    except Exception as e:
        raise OllamaUnavailableError(
            f"Could not reach Ollama at {OLLAMA_URL}. Is it running? ({e})"
        ) from e

    names = [m.get("name", "") for m in resp.json().get("models", [])]
    if not names:
        raise OllamaUnavailableError("Ollama is running but has no models pulled.")
    if preferred_model in names:
        return preferred_model, None
    fallback = names[0]
    warning = f"Model '{preferred_model}' is not pulled in Ollama; using '{fallback}' instead."
    return fallback, warning


def chat(
    messages: List[Dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
    timeout: float = 180.0,
    max_retries: int = 2,
) -> str:
    """Call Ollama's chat endpoint, retrying transient failures (timeouts,
    connection errors, 5xx) with exponential backoff. 4xx errors are not
    retried -- retrying an identical bad request just wastes time."""
    last_error: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            resp = httpx.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    # num_ctx must be bounded explicitly: this model's default context window
                    # allocates a KV cache too large for available RAM and the server OOMs.
                    "options": {"temperature": temperature, "num_predict": max_tokens, "num_ctx": 4096},
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "").strip()
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code < 500 or attempt >= max_retries:
                raise
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last_error = e
            if attempt >= max_retries:
                raise
        wait = 2 ** attempt
        time.sleep(wait)
    raise last_error  # pragma: no cover -- loop always returns or raises above


def _strip_duplicate_title_line(body: str, section_title: str) -> str:
    """Small local models often restate the section title as their own first line
    even when told not to; the caller already renders that title as a heading."""
    lines = body.split("\n", 1)
    if not lines:
        return body
    first_line = re.sub(r'^#+\s*', '', lines[0]).strip().strip('*').strip()
    if first_line.casefold() == section_title.casefold():
        return lines[1].lstrip("\n") if len(lines) > 1 else ""
    return body


def generate_section(section: Dict[str, Any], product_brief: ProductBrief, model: str) -> str:
    user_prompt = (
        f"{product_brief.context_block()}\n"
        f"Brief: {product_brief.brief}\n\n"
        f'Write the "{section["title"]}" section.\n'
        f"Section purpose: {section['description']}.\n"
        f"Target length: about {section['words']} words."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    raw = chat(messages, model=model, temperature=0.7, max_tokens=max(section["words"] * 3, 500))
    return _strip_duplicate_title_line(raw, section["title"])


def generate_product(
    product_brief: ProductBrief,
    model: str = DEFAULT_MODEL,
    on_section_done: Optional[Callable[[Dict[str, Any], str], None]] = None,
    existing_sections: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Generate content for every section of the product type. Returns {section_name: content}.

    existing_sections lets a caller resume a crashed run: sections already
    present are reused as-is (and on_section_done is not called for them),
    so only the missing ones cost a fresh model call.
    """
    structure = get_structure(product_brief.product_type)
    sections: Dict[str, str] = dict(existing_sections or {})
    for section in structure:
        if section["name"] in sections:
            continue
        section_content = generate_section(section, product_brief, model)
        sections[section["name"]] = section_content
        if on_section_done:
            on_section_done(section, section_content)
    return sections
