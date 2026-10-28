from pathlib import Path

from .base import Extracted

_converter = None

def extract(path: Path, config: dict) -> Extracted:
    if not config.get('enabled', False):
        raise RuntimeError('Docling is disabled')
    global _converter
    if _converter is None:
        from docling.document_converter import DocumentConverter
        _converter = DocumentConverter()
    result = _converter.convert(str(path))
    return Extracted(result.document.export_to_markdown(), 'docling')
