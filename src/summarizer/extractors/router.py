"""Select extractors and run configured fallback chains."""

import logging
from pathlib import Path

from . import builtin, docling, tika
from .base import Extracted

EXTRACTORS = {'builtin': builtin.extract, 'tika': tika.extract, 'docling': docling.extract}
LOG = logging.getLogger(__name__)

def extract(path: Path, config: dict) -> Extracted:
    """Extract a file, trying configured fallbacks after failures."""
    suffix = path.suffix.lower().lstrip('.')
    primary = config.get('routes', {}).get(suffix, config.get('default', 'builtin'))
    candidates = list(dict.fromkeys([primary] + list(config.get('fallback', []))))
    errors = []
    for name in candidates:
        try:
            if name not in EXTRACTORS:
                raise ValueError(f'Unknown extractor: {name}')
            LOG.info('Trying %s extractor: %s', name, path)
            extractor_config = config.get(name, config) if name != 'builtin' else config
            result = EXTRACTORS[name](path, extractor_config)
            if not result.text.strip():
                raise ValueError('Extractor returned no text')
            result.warnings.extend(errors)
            return result
        # Catch any extractor failure so the configured fallback can run.
        # Any extractor can fail; fallbacks are tried for all plugin exceptions.
        except Exception as exc:  # pylint: disable=broad-exception-caught
            LOG.warning('%s extraction failed: %s: %s', name, path, exc)
            errors.append(f'{name}: {exc}')
    raise RuntimeError('; '.join(errors))
