"""Windows single-instance guard.

A second launch of RuLens (e.g. double-clicking the shortcut again while it is
already running — possibly minimized or hidden in the tray) must NOT spawn a
duplicate process. Instead the second process signals the running ("primary")
instance to surface its window, then exits.

Mechanism (Win32, via ctypes):
- A named **mutex** detects whether an instance already exists.
- A named auto-reset **event** is the wake signal. The primary instance runs a
  background thread blocked on the event; a second instance opens the same event
  and sets it. The listener hands control back to the Tk thread through the
  app's existing UI queue (it must never touch Tk directly).

Both objects use a NULL-DACL security descriptor so an elevated and a normal
instance still share them — otherwise a process started "as administrator" and
a normal double-click would not see each other.
"""
import ctypes
import logging
import threading
from ctypes import wintypes

logger = logging.getLogger(__name__)

_MUTEX_NAME = "RuLens.ScreenTranslator.SingleInstance.Mutex"
_EVENT_NAME = "RuLens.ScreenTranslator.Show.Event"
_ERROR_ALREADY_EXISTS = 183
_WAIT_OBJECT_0 = 0x00000000
_INFINITE = 0xFFFFFFFF
_SECURITY_DESCRIPTOR_REVISION = 1
_ASFW_ANY = wintypes.DWORD(-1).value  # AllowSetForegroundWindow: any process

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
_user32 = ctypes.WinDLL("user32", use_last_error=True)

_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateEventW.restype = wintypes.HANDLE
_kernel32.CreateEventW.argtypes = [
    wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.SetEvent.argtypes = [wintypes.HANDLE]
_kernel32.SetEvent.restype = wintypes.BOOL
_kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_kernel32.WaitForSingleObject.restype = wintypes.DWORD
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL

_advapi32.InitializeSecurityDescriptor.argtypes = [wintypes.LPVOID, wintypes.DWORD]
_advapi32.InitializeSecurityDescriptor.restype = wintypes.BOOL
_advapi32.SetSecurityDescriptorDacl.argtypes = [
    wintypes.LPVOID, wintypes.BOOL, wintypes.LPVOID, wintypes.BOOL]
_advapi32.SetSecurityDescriptorDacl.restype = wintypes.BOOL


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    ]


def _shared_security_attributes():
    """SECURITY_ATTRIBUTES with a NULL DACL (accessible across integrity levels).

    Returns None on failure so callers fall back to default protection, which
    still works for the normal (same-integrity) case.
    """
    try:
        buf = ctypes.create_string_buffer(64)  # >= SECURITY_DESCRIPTOR_MIN_LENGTH (20)
        sd = ctypes.cast(buf, wintypes.LPVOID)
        if not _advapi32.InitializeSecurityDescriptor(sd, _SECURITY_DESCRIPTOR_REVISION):
            return None
        # dacl_present=True, pDacl=NULL, defaulted=False -> NULL DACL = unrestricted.
        if not _advapi32.SetSecurityDescriptorDacl(sd, True, None, False):
            return None
        sa = _SecurityAttributes()
        sa.nLength = ctypes.sizeof(_SecurityAttributes)
        sa.lpSecurityDescriptor = sd
        sa.bInheritHandle = False
        sa._buf = buf  # keep the descriptor buffer alive for the lifetime of sa
        return sa
    except OSError:
        return None


class SingleInstance:
    """Detects an existing instance and relays a 'show window' ping to it."""

    def __init__(self) -> None:
        self._mutex = None
        self._event = None
        self._sa = None
        self._listener: threading.Thread | None = None
        self._stop = False
        self.is_primary = False

    def acquire(self) -> bool:
        """Return True if this process is the first instance, else False."""
        self._sa = _shared_security_attributes()
        sa_ref = ctypes.byref(self._sa) if self._sa is not None else None
        self._mutex = _kernel32.CreateMutexW(sa_ref, False, _MUTEX_NAME)
        already = ctypes.get_last_error() == _ERROR_ALREADY_EXISTS
        self._event = _kernel32.CreateEventW(sa_ref, False, False, _EVENT_NAME)
        self.is_primary = not already
        return self.is_primary

    def signal_existing(self) -> None:
        """Ask the running instance to surface its window."""
        try:
            _user32.AllowSetForegroundWindow(_ASFW_ANY)  # let the primary take focus
        except Exception:  # noqa: BLE001 - best effort, never block exit
            pass
        if self._event:
            _kernel32.SetEvent(self._event)

    def start_listener(self, on_signal) -> None:
        """Primary only: invoke on_signal() (off the Tk thread) on each ping."""
        if not self._event:
            return

        def _wait() -> None:
            while not self._stop:
                rc = _kernel32.WaitForSingleObject(self._event, _INFINITE)
                if self._stop:
                    break
                if rc == _WAIT_OBJECT_0:
                    try:
                        on_signal()
                    except Exception as exc:  # noqa: BLE001 - keep the listener alive
                        logger.error("Не удалось показать окно по повторному запуску: %s", exc)

        self._listener = threading.Thread(
            target=_wait, name="rulens-single-instance", daemon=True)
        self._listener.start()

    def close(self) -> None:
        """Stop the listener and release the OS handles (idempotent)."""
        self._stop = True
        if self._event:
            _kernel32.SetEvent(self._event)  # wake the listener so it can exit
        if self._listener and self._listener.is_alive():
            self._listener.join(timeout=1.0)
        for handle in (self._event, self._mutex):
            if handle:
                _kernel32.CloseHandle(handle)
        self._event = None
        self._mutex = None
