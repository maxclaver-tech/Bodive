"""Opt-in long polling worker; no automatic paid-operation retry."""
import signal
import threading
import logging
from . import supervisor
from .diagnostics import category


def serve(memory, telegram):
    stop = threading.Event()
    logger = logging.getLogger("bodive.worker")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    def shutdown(signum, frame):
        stop.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    logger.info("BODIVE worker started")
    while not stop.is_set():
        try:
            acquired = supervisor.poll(memory, telegram)
            # Back off if a GitHub poll or another worker is active.
            stop.wait(1 if acquired else 5)
        except Exception as exc:
            # Never log exception content: provider and DB errors may contain secrets.
            logger.warning("Poll failed (%s); next poll in 15 seconds", category(exc))
            stop.wait(15)
    logger.info("BODIVE worker stopped")
