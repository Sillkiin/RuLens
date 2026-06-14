"""Root conftest — its directory is added to sys.path by pytest, so `import rulens` works.

Also provides ONE session-wide Tk root: creating/destroying multiple tk.Tk() roots in a
single process corrupts the Tcl interpreter on Windows.
"""
import tkinter as tk

import pytest


@pytest.fixture(scope="session")
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass
