import threading

import pytest

from summarizer import progress


def test_activity_heartbeat_and_cleanup(monkeypatch, caplog):
    caplog.set_level('INFO', logger='summarizer')
    heartbeat_seen = threading.Event()
    original_info = progress.LOG.info
    workers_before = set(threading.enumerate())

    def info(message, *args):
        original_info(message, *args)
        if message.startswith('Still working:'):
            heartbeat_seen.set()

    monkeypatch.setattr(progress.LOG, 'info', info)
    with progress.activity('Extracting file: /documents/large.pdf', interval=0.01):
        assert heartbeat_seen.wait(timeout=2)
    assert 'Still working: Extracting file: /documents/large.pdf' in caplog.text
    assert 'elapsed)' in caplog.text
    assert 'Finished: Extracting file: /documents/large.pdf' in caplog.text
    assert set(threading.enumerate()) == workers_before


def test_activity_failure_is_reported_and_propagated(caplog):
    caplog.set_level('INFO', logger='summarizer')
    workers_before = set(threading.enumerate())
    with pytest.raises(RuntimeError, match='model unavailable'), progress.activity('document summary: /documents/file.txt'):
        raise RuntimeError('model unavailable')
    assert 'Stopped: document summary: /documents/file.txt' in caplog.text
    assert 'Finished:' not in caplog.text
    assert set(threading.enumerate()) == workers_before
