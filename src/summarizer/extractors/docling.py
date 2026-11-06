"""Optional Docling based document extraction."""

from functools import lru_cache
from pathlib import Path

from .base import Extracted


@lru_cache(maxsize=1)
def _get_converter(ocr_languages: tuple[str, ...]):
    """Load and reuse the optional Docling converter configured with Tesseract."""
    # Docling is an optional extra; delay its import until enabled extraction.
    # pylint: disable=import-outside-toplevel,import-error
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        TesseractCliOcrOptions,
    )
    from docling.document_converter import DocumentConverter
    from docling.document_converter import ImageFormatOption, PdfFormatOption

    def pipeline_options():
        return PdfPipelineOptions(
            do_ocr=True,
            ocr_options=TesseractCliOcrOptions(lang=list(ocr_languages)),
        )

    format_options = {
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options()),
        InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_options()),
    }
    return DocumentConverter(format_options=format_options)


def extract(path: Path, config: dict) -> Extracted:
    """Extract a document with Docling when it is enabled."""
    if not config.get('enabled', False):
        raise RuntimeError('Docling is disabled')
    language = str(config.get('ocr_language', 'eng')).strip()
    ocr_languages = tuple(
        part.strip() for part in language.replace(',', '+').split('+') if part.strip())
    if not ocr_languages:
        raise ValueError(
            'extraction.docling.ocr_language must contain a Tesseract language code')
    result = _get_converter(ocr_languages).convert(str(path))
    return Extracted(result.document.export_to_markdown(), 'docling')
