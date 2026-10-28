"""Optional Docling-backed document extractor."""

from functools import lru_cache
from pathlib import Path

from .base import Extracted

def extract(path: Path, config: dict) -> Extracted:
    """Extract a document as Markdown with Docling."""
    if not config.get('enabled', False):
        raise RuntimeError('Docling is disabled')
    result = _get_converter().convert(str(path))
    return Extracted(result.document.export_to_markdown(), 'docling')


@lru_cache(maxsize=1)
def _get_converter():
    """Create the optional converter only when Docling is enabled and used."""
    # The dependency is optional, so it must be imported only when called.
    # pylint: disable=import-outside-toplevel,import-error
    from docling.document_converter import DocumentConverter

    return DocumentConverter()
