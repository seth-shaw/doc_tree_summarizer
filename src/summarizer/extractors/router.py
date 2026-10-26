from pathlib import Path
from .base import Extracted
from . import builtin, tika, docling

EXTRACTORS = {'builtin': builtin.extract, 'tika': tika.extract, 'docling': docling.extract}

def extract(path: Path, config: dict) -> Extracted:
    suffix = path.suffix.lower().lstrip('.')
    primary = config.get('routes', {}).get(suffix, config.get('default', 'builtin'))
    candidates = list(dict.fromkeys([primary] + list(config.get('fallback', []))))
    errors = []
    for name in candidates:
        try:
            if name not in EXTRACTORS:
                raise ValueError(f'Unknown extractor: {name}')
            result = EXTRACTORS[name](path, config.get(name, config) if name != 'builtin' else config)
            if not result.text.strip():
                raise ValueError('Extractor returned no text')
            result.warnings.extend(errors)
            return result
        except Exception as exc:
            errors.append(f'{name}: {exc}')
    raise RuntimeError('; '.join(errors))
