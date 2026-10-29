"""Optional Docling based document extraction."""

from functools import lru_cache
from pathlib import Path

from .base import Extracted


@lru_cache(maxsize=1)
def _get_converter():
    """Load and reuse the optional Docling converter."""
    # Docling is an optional extra; delay its import until enabled extraction.
    # pylint: disable=import-outside-toplevel,import-error
    from docling.document_converter import DocumentConverter

    return DocumentConverter()


def extract(path: Path, config: dict) -> Extracted:
    """Extract a document with Docling when it is enabled."""
    if not config.get('enabled', False):
        raise RuntimeError('Docling is disabled')
    result = _get_converter().convert(str(path))
    return Extracted(result.document.export_to_markdown(), 'docling')
