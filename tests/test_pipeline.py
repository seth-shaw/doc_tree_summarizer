"""Tests for document tree summarization."""

from summarizer.cache import Cache
from summarizer.pipeline import DOCUMENT_PROMPT, chunks, run, summarize_long


# These minimal doubles implement only the protocol methods the tested pipeline
# calls, rather than unrelated behavior from a full production model client.
# pylint: disable=too-few-public-methods
class FakeModel:
    """Provide deterministic summaries for pipeline tests."""
    def summarize(self, _model, _system, content):
        """Return fixed text containing the start of the supplied content."""
        return 'SYNTHESIS: ' + content[:200]


def test_chunks():
    """Verify that chunking preserves all input characters."""
    assert ''.join(chunks('a' * 250, 100)) == 'a' * 250


def test_hierarchy_and_html(tmp_path, caplog):
    """Verify hierarchical summaries, report output, and cache reuse."""
    caplog.set_level('INFO', logger='summarizer')
    root = tmp_path / 'collection'
    child = root / 'child'
    child.mkdir(parents=True)
    (child / 'one.txt').write_text('interview notes')
    (root / 'two.md').write_text('overview')
    config = {
        'extraction': {
            'routes': {'txt': 'builtin', 'md': 'builtin'},
            'default': 'builtin', 'fallback': [], 'ocr': {},
        },
        'summarization': {
            'document_model': 'fake', 'directory_model': 'fake-directory',
            'chunk_chars': 1000, 'chunk_overlap_chars': 0, 'group_chars': 1000,
        },
        'output': {},
    }
    cache = Cache(tmp_path / 'state.sqlite3')
    report = tmp_path / 'report.html'
    result = run(root, config, cache, FakeModel(), report)
    assert result['status'] == 'ok'
    assert [n['name'] for n in result['children']] == ['child', 'two.md']
    assert result['children'][0]['children'][0]['name'] == 'one.txt'
    assert 'SYNTHESIS' in report.read_text()
    assert f'Entering directory: {child}' in caplog.text
    assert f'Processing file: {child / "one.txt"}' in caplog.text
    assert f'Extracting file: {child / "one.txt"}' in caplog.text
    assert f'document summary: {child / "one.txt"} (chunk 1/1, model fake)' in caplog.text
    assert f'Summarizing directory: {root}' in caplog.text
    assert 'Run complete: 2 files processed, 0 files failed, 2 directories completed' in caplog.text
    metadata = cache.db.execute('SELECT stage, path, filename, model FROM cache_entries').fetchall()
    assert ('extraction', str(child / 'one.txt'), 'one.txt', None) in metadata
    assert ('document', str(child / 'one.txt'), 'one.txt', 'fake') in metadata
    assert ('directory', str(root), root.name, 'fake-directory') in metadata
    # Simulate results from a run before source metadata was introduced.
    cache.db.execute('DELETE FROM cache_contexts')
    cache.db.commit()
    caplog.clear()

    # This one-method test double makes unexpected cache misses fail immediately.
    # pylint: disable=too-few-public-methods
    class CachedModel:
        """Fail if a cache hit unexpectedly calls the model."""
        def summarize(self, *_args):
            """Fail if the pipeline tries to generate a cached summary."""
            raise AssertionError('Cached runs must not call the model')

    assert run(root, config, cache, CachedModel(), report) == result
    assert f'Extraction cache hit: {child / "one.txt"}' in caplog.text
    assert f'Cache hit: document summary: {child / "one.txt"}' in caplog.text
    assert f'Cache hit: directory summary: {root}' in caplog.text
    assert sorted(cache.db.execute(
        'SELECT stage, path, filename, model FROM cache_entries').fetchall()) == sorted(metadata)
    cache.close()


def test_chunk_and_reduction_progress(tmp_path, caplog):
    """Verify progress is reported for chunking and reduction."""
    caplog.set_level('INFO', logger='summarizer')

    # This one-method test double supplies a bounded response for reductions.
    # pylint: disable=too-few-public-methods
    class ShortModel:
        """Return a short fixed summary for chunking tests."""
        def summarize(self, *_args):
            """Return a short response regardless of the request contents."""
            return 'Short summary'

    cache = Cache(tmp_path / 'cache.sqlite3')
    try:
        answer = summarize_long('x' * 250, 'fake', DOCUMENT_PROMPT,
                                {'chunk_chars': 100, 'chunk_overlap_chars': 0, 'group_chars': 1000},
                                ShortModel(), cache, 'document', tmp_path / 'large.txt')
        assert answer == 'Short summary'
        assert 'chunk 1/3' in caplog.text
        assert 'chunk 3/3' in caplog.text
        assert 'reduction round 1, group 1/1' in caplog.text
    finally:
        cache.close()


def test_failed_file_progress(tmp_path, caplog):
    """Verify file failures are reported while processing continues."""
    caplog.set_level('INFO', logger='summarizer')
    (tmp_path / 'bad.pdf').write_bytes(b'not a PDF')
    config = {'extraction': {'routes': {'pdf': 'missing'}, 'fallback': []},
              'summarization': {}, 'output': {}}
    cache = Cache(tmp_path / 'state.sqlite3')
    try:
        result = run(tmp_path, config, cache, FakeModel(), tmp_path / 'report.html')
        assert result['status'] == 'failed'
        assert 'status=failed' in caplog.text
        assert 'Run complete: 1 files processed, 1 files failed' in caplog.text
    finally:
        cache.close()
