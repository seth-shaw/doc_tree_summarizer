from pathlib import Path
from summarizer.cache import Cache
from summarizer.pipeline import run, chunks

class FakeModel:
    def summarize(self, model, system, content):
        return 'SYNTHESIS: ' + content[:200]

def test_chunks():
    assert ''.join(chunks('a' * 250, 100)) == 'a' * 250

def test_hierarchy_and_html(tmp_path):
    root = tmp_path / 'collection'
    child = root / 'child'
    child.mkdir(parents=True)
    (child / 'one.txt').write_text('interview notes')
    (root / 'two.md').write_text('overview')
    config = {'extraction': {'routes': {'txt': 'builtin', 'md': 'builtin'}, 'default': 'builtin', 'fallback': [], 'ocr': {}},
              'summarization': {'document_model': 'fake', 'directory_model': 'fake', 'chunk_chars': 1000,
                                'chunk_overlap_chars': 0, 'group_chars': 1000}, 'output': {}}
    cache = Cache(tmp_path / 'state.sqlite3')
    report = tmp_path / 'report.html'
    result = run(root, config, cache, FakeModel(), report)
    assert result['status'] == 'ok'
    assert [n['name'] for n in result['children']] == ['child', 'two.md']
    assert result['children'][0]['children'][0]['name'] == 'one.txt'
    assert 'SYNTHESIS' in report.read_text()
    cache.close()
