from __future__ import annotations

import signal
from unittest.mock import MagicMock, call, patch

import pytest

from ansible.executor.task_queue_manager import TaskQueueManager


def test_signal_handler_skips_inherited_worker() -> None:
    worker = MagicMock(pid=11)
    worker.is_alive.side_effect = AssertionError('can only test a child process')
    task_queue_manager = object.__new__(TaskQueueManager)
    task_queue_manager._workers = [worker]

    with (
        patch('ansible.executor.task_queue_manager.signal.signal') as signal_mock,
        patch('ansible.executor.task_queue_manager.os.getpid', return_value=22),
        patch('ansible.executor.task_queue_manager.os.kill') as kill_mock,
    ):
        task_queue_manager._signal_handler(signal.SIGTERM, None)

    signal_mock.assert_called_once_with(signal.SIGTERM, signal.SIG_DFL)
    kill_mock.assert_called_once_with(22, signal.SIGTERM)


def test_signal_handler_propagates_signal_to_live_workers() -> None:
    stopped_worker = MagicMock(pid=11)
    stopped_worker.is_alive.return_value = False
    running_worker = MagicMock(pid=22)
    running_worker.is_alive.return_value = True
    task_queue_manager = object.__new__(TaskQueueManager)
    task_queue_manager._workers = [None, stopped_worker, running_worker]

    with (
        patch('ansible.executor.task_queue_manager.signal.signal'),
        patch('ansible.executor.task_queue_manager.os.getpid', return_value=33),
        patch('ansible.executor.task_queue_manager.os.kill') as kill_mock,
    ):
        task_queue_manager._signal_handler(signal.SIGTERM, None)

    kill_mock.assert_has_calls((call(22, signal.SIGTERM), call(33, signal.SIGTERM)))
    assert kill_mock.call_count == 2


def test_signal_handler_defers_sigint_after_worker_propagation() -> None:
    worker = MagicMock(pid=11)
    worker.is_alive.return_value = True
    task_queue_manager = object.__new__(TaskQueueManager)
    task_queue_manager._workers = [worker]

    with (
        patch('ansible.executor.task_queue_manager.signal.signal'),
        patch('ansible.executor.task_queue_manager.os.getpid') as getpid_mock,
        patch('ansible.executor.task_queue_manager.os.kill') as kill_mock,
        pytest.raises(KeyboardInterrupt),
    ):
        task_queue_manager._signal_handler(signal.SIGINT, None)

    kill_mock.assert_called_once_with(11, signal.SIGINT)
    getpid_mock.assert_not_called()
