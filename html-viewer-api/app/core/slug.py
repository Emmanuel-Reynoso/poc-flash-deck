"""URL-safe names for the readable links: /u/{handle}/{slug}."""

from __future__ import annotations

import re
import unicodedata

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_SLUG_LENGTH = 60


def slugify(text: str, max_length: int = MAX_SLUG_LENGTH) -> str:
    """Lowercase ASCII letters and digits separated by single dashes. May return ''."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug[:max_length].strip("-")


def is_slug(value: str) -> bool:
    return len(value) <= MAX_SLUG_LENGTH + 8 and bool(SLUG_RE.match(value))
