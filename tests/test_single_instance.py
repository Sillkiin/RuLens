"""Single-instance guard: mutex detection + event-driven 'show' relay.

These run in one process using two SingleInstance objects sharing the same named
mutex/event, so they are deterministic and need no subprocess.
"""
import sys
import threading

import pytest

if sys.platform != "win32":  # pragma: no cover - Windows-only mechanism
    pytest.skip("single-instance guard is Windows-only", allow_module_level=True)

from rulens.single_instance import SingleInstance


def test_first_is_primary_second_is_not():
    first = SingleInstance()
    second = SingleInstance()
    try:
        assert first.acquire() is True       # first one owns the slot
        assert second.acquire() is False     # named mutex already exists
        assert first.is_primary is True
        assert second.is_primary is False
    finally:
        first.close()
        second.close()


def test_signal_relays_to_primary_listener():
    primary = SingleInstance()
    other = SingleInstance()
    fired = threading.Event()
    try:
        assert primary.acquire() is True
        primary.start_listener(fired.set)
        assert other.acquire() is False
        other.signal_existing()
        assert fired.wait(timeout=3.0), "primary listener was not pinged"
    finally:
        primary.close()
        other.close()


def test_close_is_idempotent():
    inst = SingleInstance()
    inst.acquire()
    inst.close()
    inst.close()  # second close must not raise
