"""Apache Tika server-backed document extractor."""

import urllib.request
from pathlib import Path

from .base import Extracted


def extract(path: Path, config: dict) -> Extracted:
    """Send a document to the configured Tika server and return its text."""
    if not config.get('enabled', False):
        raise RuntimeError('Tika is disabled')
    url = config.get('url', 'http://127.0.0.1:9998').rstrip('/') + '/tika'
    data = path.read_bytes()
    req = urllib.request.Request(url, data=data, method='PUT', headers={
        'Accept': 'text/plain', 'Content-Type': 'application/octet-stream',
        'Content-Disposition': f'attachment; filename="{path.name.replace(chr(34), "")}"',
    })
    with urllib.request.urlopen(req, timeout=int(config.get('timeout_seconds', 180))) as response:
        text = response.read().decode('utf-8', errors='replace')
    return Extracted(text, 'tika')
