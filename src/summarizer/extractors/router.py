"""Route documents to configured extraction backends."""

import logging
from pathlib import Path

from . import builtin, docling, tika
from .base import Extracted

EXTRACTORS = {'builtin': builtin.extract, 'tika': tika.extract, 'docling': docling.extract}
LOG = logging.getLogger(__name__)


def extract(path: Path, config: dict, mime: str | None = None) -> Extracted:
    """Extract text using a detected media type, then configured fallbacks.

    Route keys may be media types (for example ``application/pdf``) or file
    extensions. Media type routes take precedence when detection recognizes a
    configured type; extensions remain useful for formats the detector cannot
    identify, such as plain text and some archive-based office formats.
    """
    suffix = path.suffix.lower().lstrip('.')
    routes = config.get('routes', {})
    if mime:
        primary = routes.get(mime, config.get('default', 'tika'))
    else:
        primary = routes.get(suffix, config.get('default', 'tika'))
    candidates = list(dict.fromkeys([primary] + list(config.get('fallback', []))))
    errors = []
    for name in candidates:
        try:
            if name not in EXTRACTORS:
                raise ValueError(f'Unknown extractor: {name}')
            LOG.info('Trying %s extractor: %s', name, path)
            result = EXTRACTORS[name](path, config.get(name, config)
                                      if name != 'builtin' else config)
            if not result.text.strip():
                raise ValueError('Extractor returned no text')
            result.warnings.extend(errors)
            return result
        # Optional extractors can fail with different exception types. The router
        # records a backend failure and tries the next configured fallback.
        except Exception as exc:  # pylint: disable=broad-exception-caught
            LOG.warning('%s extraction failed: %s: %s', name, path, exc)
            errors.append(f'{name}: {exc}')
    raise RuntimeError('; '.join(errors))
