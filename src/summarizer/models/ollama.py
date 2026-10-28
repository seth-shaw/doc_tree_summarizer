"""HTTP client for text and vision requests to Ollama."""

import base64
import json
import logging
import time
import urllib.error
import urllib.request

LOG = logging.getLogger(__name__)

class Ollama:
    """Call an Ollama server using the configured model options."""

    def __init__(self, config: dict):
        """Save the model and server configuration."""
        self.config = config

    def summarize(self, model: str, system: str, content: str) -> str:
        """Request a text summary, retrying transient server failures."""
        cfg = self.config
        payload = {
            'model': model, 'stream': False,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': content},
            ],
            'options': {
                'temperature': cfg.get('temperature', 0.1),
                'num_ctx': cfg.get('context_tokens', 32768),
                'num_predict': cfg.get('max_output_tokens', 1200),
            },
            'think': bool(cfg.get('thinking', False)),
        }
        request_data = json.dumps(payload).encode('utf-8')
        for attempt in range(int(cfg.get('retries', 2)) + 1):
            try:
                request = urllib.request.Request(
                    cfg.get('ollama_url', 'http://127.0.0.1:11434').rstrip('/') + '/api/chat',
                    data=request_data, method='POST',
                    headers={'Content-Type': 'application/json'},
                )
                timeout = int(cfg.get('timeout_seconds', 900))
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    answer = json.load(response)['message']['content'].strip()
                if not answer:
                    raise RuntimeError('Empty model response')
                return answer
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError,
                    KeyError, RuntimeError) as exc:
                if attempt == int(cfg.get('retries', 2)):
                    raise
                delay = min(2 ** attempt, 10)
                LOG.warning(
                    'Ollama request failed for model %s (attempt %d/%d): %s; retrying in %ds',
                    model, attempt + 1, int(cfg.get('retries', 2)) + 1, exc, delay,
                )
                time.sleep(delay)
        raise RuntimeError('Unreachable')

    def characterize_image(self, model: str, images: list[bytes]) -> dict:
        """Classify an image and describe its visible content using an Ollama vision model."""
        payload = self._image_payload(model, images)
        return self._request_image_characterization(model, payload)

    def _image_payload(self, model: str, images: list[bytes]) -> dict:
        """Build the structured output request for image characterization."""
        prompt = (
            'Inspect the image or image pages. Return JSON with exactly these keys: '
            '"kind" and "description". Set kind to "scanned_document" only when the main '
            'content is a scanned or photographed document page intended to be read. Use '
            '"photograph" for ordinary digital photos, including photos containing incidental '
            'text, and "other" for diagrams, artwork, screenshots, or unclear content. '
            'Describe the visible content, including any context useful for identifying it. '
            'Do not transcribe text in detail; OCR will run separately for scanned documents.'
        )
        return {
            'model': model,
            'stream': False,
            'format': {
                'type': 'object',
                'properties': {
                    'kind': {'type': 'string', 'enum': ['scanned_document', 'photograph', 'other']},
                    'description': {'type': 'string'},
                },
                'required': ['kind', 'description'],
            },
            'messages': [{'role': 'user', 'content': prompt,
                          'images': [base64.b64encode(image).decode('ascii') for image in images]}],
            'options': {
                'temperature': 0.1,
                'num_ctx': self.config.get('context_tokens', 32768),
                'num_predict': 500,
            },
            'think': bool(self.config.get('thinking', False)),
        }

    def _request_image_characterization(self, model: str, payload: dict) -> dict:
        """Send and validate an image request, retrying transient failures."""
        request_data = json.dumps(payload).encode('utf-8')
        retries = int(self.config.get('retries', 2))
        for attempt in range(retries + 1):
            try:
                request = urllib.request.Request(
                    self.config.get('ollama_url', 'http://127.0.0.1:11434').rstrip('/')
                    + '/api/chat',
                    data=request_data, method='POST',
                    headers={'Content-Type': 'application/json'},
                )
                with urllib.request.urlopen(
                    request, timeout=int(self.config.get('timeout_seconds', 900))
                ) as response:
                    answer = json.load(response)['message']['content'].strip()
                result = json.loads(answer)
                if result.get('kind') not in {'scanned_document', 'photograph', 'other'}:
                    raise ValueError('Image model returned an invalid kind')
                description = result.get('description')
                if not isinstance(description, str) or not description.strip():
                    raise ValueError('Image model returned no description')
                return result
            except urllib.error.HTTPError as exc:
                details = exc.read().decode('utf-8', errors='replace').strip()
                if 'unknown model architecture' in details.lower():
                    raise RuntimeError(
                        f'Ollama cannot load {model!r}: its runner does not recognize '
                        'the architecture. Use a different vision model such as '
                        'qwen2.5vl:3b (set extraction.image.model '
                        'and run `ollama pull qwen2.5vl:3b`), or update Ollama. '
                        f'Ollama response: {details}'
                    ) from exc
                if exc.code == 404:
                    raise RuntimeError(
                        f'Ollama returned HTTP 404 for image model {model!r}. '
                        f'Check extraction.image.model and pull it with `ollama pull {model}`. '
                        f'Ollama response: {details or exc.reason}'
                    ) from exc
                if 400 <= exc.code < 500:
                    raise RuntimeError(
                        f'Ollama rejected image characterization with HTTP {exc.code}: '
                        f'{details or exc.reason}'
                    ) from exc
                if attempt == retries:
                    raise RuntimeError(
                        f'Ollama image characterization failed with HTTP {exc.code}: '
                        f'{details or exc.reason}'
                    ) from exc
                delay = min(2 ** attempt, 10)
                LOG.warning(
                    'Ollama image request failed for model %s (attempt %d/%d): '
                    'HTTP %d: %s; retrying in %ds',
                    model, attempt + 1, retries + 1, exc.code, details or exc.reason, delay,
                )
                time.sleep(delay)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError,
                    ValueError, KeyError, RuntimeError) as exc:
                if attempt == retries:
                    raise
                delay = min(2 ** attempt, 10)
                LOG.warning(
                    'Ollama image request failed for model %s (attempt %d/%d): %s; '
                    'retrying in %ds',
                    model, attempt + 1, retries + 1, exc, delay,
                )
                time.sleep(delay)
        raise RuntimeError('Unreachable')
