from __future__ import annotations

import html
import re

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"[ \t]+")


def html_to_text(raw: str) -> str:
    """Strip tags from ATS-provided job description HTML into plain text.

    Greenhouse's `content` field is HTML-escaped HTML (entities like `&lt;div&gt;`),
    so unescape first, then strip the resulting tags.
    """
    unescaped = html.unescape(raw)
    no_tags = _TAG_RE.sub(" ", unescaped)
    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in no_tags.splitlines()]
    return "\n".join(line for line in lines if line)
