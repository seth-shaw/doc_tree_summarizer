import shutil
import subprocess
import tempfile
from pathlib import Path

from .base import Extracted

TEXT = {'.txt', '.md', '.markdown', '.csv', '.json', '.xml', '.rst', '.log'}
HTML = {'.html', '.htm'}

def _ocr_pdf(path: Path, target: Path, ocr: dict, mode: str) -> None:
    backend = ocr.get('backend', 'docker')
    options = ['--rotate-pages', '--deskew', '--jobs', '2', '-l', str(ocr.get('language', 'eng')),
               '--force-ocr' if mode == 'always' else '--skip-text']
    if backend == 'docker':
        if not shutil.which('docker'):
            raise RuntimeError('PDF OCR needs Docker with Compose; install and start Docker Desktop')
        compose_file = Path(ocr.get('compose_file', Path(__file__).resolve().parents[3] / 'compose.yaml')).expanduser().resolve()
        if not compose_file.is_file():
            raise RuntimeError('OCR Compose file not found; set extraction.ocr.compose_file to its absolute path')
        command = ['docker', 'compose', '-f', str(compose_file), 'run', '--rm', '--no-deps', '-T',
                   'ocrmypdf', *options, '-', '-']
        # Stream PDF bytes directly: no host mounts or container-owned output files.
        with path.open('rb') as source, target.open('wb') as output:
            result = subprocess.run(command, stdin=source, stdout=output, stderr=subprocess.PIPE,
                                    text=True, timeout=3600)
    elif backend == 'native':
        if not shutil.which('ocrmypdf'):
            raise RuntimeError('PDF OCR needs native ocrmypdf; install it or set extraction.ocr.backend to docker')
        result = subprocess.run(['ocrmypdf', *options, str(path), str(target)],
                                capture_output=True, text=True, timeout=3600)
    else:
        raise ValueError('extraction.ocr.backend must be docker or native')
    if result.returncode != 0:
        raise RuntimeError('OCR failed: ' + result.stderr[-1500:])

def extract(path: Path, config: dict) -> Extracted:
    suffix = path.suffix.lower()
    if suffix in TEXT:
        return Extracted(path.read_text(encoding='utf-8', errors='replace'), 'builtin:text')
    if suffix in HTML:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(path.read_text(encoding='utf-8', errors='replace'), 'html.parser')
        for element in soup(['script', 'style', 'noscript']):
            element.decompose()
        return Extracted(soup.get_text('\n', strip=True), 'builtin:html')
    if suffix == '.docx':
        from docx import Document
        doc = Document(str(path))
        pieces = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                pieces.append(' | '.join(cell.text.replace('\n', ' ') for cell in row.cells))
        return Extracted('\n\n'.join(pieces), 'builtin:docx', ['Embedded images and textboxes may not be extracted.'])
    if suffix == '.pdf':
        import fitz
        ocr = config.get('ocr', {})
        mode = ocr.get('mode', 'auto')
        if mode not in ('off', 'auto', 'always'):
            raise ValueError('extraction.ocr.mode must be off, auto, or always')
        with fitz.open(path) as pdf:
            pages = [p.get_text('text').strip() for p in pdf]
        threshold = int(ocr.get('min_chars_per_page', 40))
        needs_ocr = mode == 'always' or (mode == 'auto' and any(len(p) < threshold for p in pages))
        warnings = []
        if needs_ocr:
            with tempfile.TemporaryDirectory(prefix='local-ai-ocr-') as tmp:
                target = Path(tmp) / 'ocr.pdf'
                _ocr_pdf(path, target, ocr, mode)
                with fitz.open(target) as pdf:
                    pages = [p.get_text('text').strip() for p in pdf]
            warnings.append('OCR applied; verify recognition accuracy.')
        return Extracted('\n\n'.join(f'[Page {i + 1}]\n{p}' for i, p in enumerate(pages) if p), 'builtin:pdf', warnings)
    raise ValueError(f'Unsupported builtin format: {suffix}')
