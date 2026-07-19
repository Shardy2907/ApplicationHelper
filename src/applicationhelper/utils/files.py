from __future__ import annotations

from pathlib import Path


def extract_docx_text(path: Path) -> str:
    import docx

    document = docx.Document(str(path))
    return "\n".join(p.text for p in document.paragraphs if p.text.strip())


def extract_pdf_text(path: Path) -> str:
    """Best-effort text fallback. The parser agent prefers sending the PDF
    directly to Claude as a native document content block; this is only used
    where plain text is needed (e.g. non-Claude paths, fixtures, tests)."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
