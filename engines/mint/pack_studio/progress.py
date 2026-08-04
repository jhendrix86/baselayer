"""
Pack Studio - Progress / Resume

Persists partial results for a pack build so a crashed or interrupted run
(a flaky Ollama call, a closed terminal) doesn't have to restart from
scratch -- a full run makes 10-20 sequential model calls and can take
several minutes. Keyed to a hash of the brief's inputs, so editing the
brief and rerunning starts fresh instead of silently mixing stale content
generated under the old brief with the new one.

This is a crash-recovery checkpoint, not a permanent cache: it's deleted
once a build completes successfully.
"""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

from .brief import ProductBrief


def _brief_hash(product_brief: ProductBrief) -> str:
    payload = json.dumps(asdict(product_brief), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Progress:
    def __init__(self, output_dir: Path, product_brief: ProductBrief, fresh: bool = False):
        self.path = output_dir / ".progress.json"
        self.brief_hash = _brief_hash(product_brief)
        self.data: Dict[str, Any] = {"brief_hash": self.brief_hash, "sections": {}, "marketing_kit": {}}
        self.resumed = False

        if fresh:
            self.clear()
            return

        if self.path.exists():
            try:
                stored = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                stored = {}
            if stored.get("brief_hash") == self.brief_hash:
                self.data = stored
                self.resumed = bool(
                    self.data.get("sections") or self.data.get("listing_data") or self.data.get("marketing_kit")
                )

    def sections(self) -> Dict[str, str]:
        return self.data.get("sections", {})

    def save_section(self, name: str, text: str) -> None:
        self.data.setdefault("sections", {})[name] = text
        self._flush()

    def listing_data(self) -> Optional[Dict[str, Any]]:
        return self.data.get("listing_data")

    def save_listing(self, listing_data: Dict[str, Any]) -> None:
        self.data["listing_data"] = listing_data
        self._flush()

    def marketing_kit(self) -> Dict[str, str]:
        return self.data.get("marketing_kit", {})

    def save_marketing_platform(self, key: str, text: str) -> None:
        self.data.setdefault("marketing_kit", {})[key] = text
        self._flush()

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def _flush(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
