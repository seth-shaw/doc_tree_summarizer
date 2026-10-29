"""Progress activity logging and heartbeat support."""

import logging
import threading
import time
from contextlib import contextmanager

LOG = logging.getLogger(__name__)


@contextmanager
def activity(description: str, interval: float = 60):
    """Report the active operation, including while a blocking call is running."""
    started = time.monotonic()
    stopped = threading.Event()

    def heartbeat():
        """Heartbeat."""
        while not stopped.wait(interval):
            LOG.info('Still working: %s (%.1fs elapsed)', description, time.monotonic() - started)

    LOG.info('Starting: %s', description)
    worker = threading.Thread(target=heartbeat, daemon=True)
    worker.start()
    try:
        yield
    except BaseException:
        LOG.info('Stopped: %s (%.1fs elapsed)', description, time.monotonic() - started)
        raise
    else:
        LOG.info('Finished: %s (%.1fs)', description, time.monotonic() - started)
    finally:
        stopped.set()
        worker.join()
