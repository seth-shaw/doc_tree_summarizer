import json
import time
import urllib.request

class Ollama:
    def __init__(self, config: dict):
        self.config = config

    def summarize(self, model: str, system: str, content: str) -> str:
        cfg = self.config
        payload = {
            'model': model, 'stream': False,
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': content}],
            'options': {'temperature': cfg.get('temperature', 0.1), 'num_ctx': cfg.get('context_tokens', 32768), 'num_predict': cfg.get('max_output_tokens', 1200)},
            'think': bool(cfg.get('thinking', False)),
        }
        request_data = json.dumps(payload).encode('utf-8')
        for attempt in range(int(cfg.get('retries', 2)) + 1):
            try:
                request = urllib.request.Request(cfg.get('ollama_url', 'http://127.0.0.1:11434').rstrip('/') + '/api/chat',
                                                 data=request_data, method='POST', headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(request, timeout=int(cfg.get('timeout_seconds', 900))) as response:
                    answer = json.load(response)['message']['content'].strip()
                if not answer:
                    raise RuntimeError('Empty model response')
                return answer
            except Exception:
                if attempt == int(cfg.get('retries', 2)):
                    raise
                time.sleep(min(2 ** attempt, 10))
        raise RuntimeError('Unreachable')
