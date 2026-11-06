"""Built-in text, HTML, and Word extraction."""

from pathlib import Path

from .base import Extracted

TEXT = {'.txt', '.md', '.markdown', '.csv', '.json', '.xml', '.rst', '.log'}
HTML = {'.html', '.htm'}


# This dispatcher keeps format selection in one place; its locals track the
# per-format intermediate data needed to produce a consistent Extracted value.
# pylint: disable=too-many-locals
def extract(path: Path, _config: dict) -> Extracted:
    """Extract text from a file using its configured format handler."""
    suffix = path.suffix.lower()
    if suffix in TEXT:
        return Extracted(path.read_text(encoding='utf-8', errors='replace'), 'builtin:text')
    if suffix in HTML:
        # BeautifulSoup is an optional dependency used only for HTML inputs.
        # pylint: disable=import-outside-toplevel
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(path.read_text(encoding='utf-8', errors='replace'), 'html.parser')
        for element in soup(['script', 'style', 'noscript']):
            element.decompose()
        return Extracted(soup.get_text('\n', strip=True), 'builtin:html')
    if suffix == '.docx':
        # python-docx is optional and should only be imported for Word files.
        # pylint: disable=import-outside-toplevel
        from docx import Document
        doc = Document(str(path))
        pieces = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                pieces.append(' | '.join(cell.text.replace('\n', ' ') for cell in row.cells))
        warning = 'Embedded images and textboxes may not be extracted.'
        return Extracted('\n\n'.join(pieces), 'builtin:docx', [warning])
    raise ValueError(f'Unsupported builtin format: {suffix}')
