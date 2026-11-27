import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch
from bodive import supervisor

class WorkerLockTests(unittest.TestCase):
    def test_locked_worker_does_not_consume_updates(self):
        memory, telegram = Mock(), Mock()
        @contextmanager
        def lock():
            yield False
        memory.poll_lock.side_effect = lock
        self.assertFalse(supervisor.poll(memory, telegram))
        telegram.updates.assert_not_called()

    def test_acquired_lock_runs_one_poll(self):
        memory, telegram = Mock(), Mock()
        @contextmanager
        def lock():
            yield True
        memory.poll_lock.side_effect = lock
        with patch("bodive.supervisor._poll_locked") as poll:
            self.assertTrue(supervisor.poll(memory, telegram))
            poll.assert_called_once_with(memory, telegram)
