"""Single-instance guard: mutex detection + event-driven 'show' relay.

Each test uses UNIQUE named objects (via the `names` fixture) so it never collides
with a running RuLens.exe (which holds the production mutex) or with other tests.
"""
import sys
import threading
import uuid

import pytest

if sys.platform != "win32":  # pragma: no cover - Windows-only mechanism
    pytest.skip("single-instance guard is Windows-only", allow_module_level=True)

from rulens.single_instance import SingleInstance


@pytest.fixture
def names():
    uid = uuid.uuid4().hex
    return f"RuLens.Test.{uid}.Mutex", f"RuLens.Test.{uid}.Event"


def test_first_is_primary_second_is_not(names):
    first = SingleInstance(*names)
    second = SingleInstance(*names)
    try:
        assert first.acquire() is True       # first one owns the slot
        assert second.acquire() is False     # named mutex already exists
        assert first.is_primary is True
        assert second.is_primary is False
    finally:
        first.close()
        second.close()


def test_signal_relays_to_primary_listener(names):
    primary = SingleInstance(*names)
    other = SingleInstance(*names)
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


def test_close_is_idempotent(names):
    inst = SingleInstance(*names)
    inst.acquire()
    inst.close()
    inst.close()  # second close must not raise
