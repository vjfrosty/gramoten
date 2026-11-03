"""Where the package's word lists are: `DATA`, a real folder on disk.

Found through `importlib.resources`, so it also works when the package is not a plain
folder (a zip app): the lists are then unpacked once, for the life of the process,
since `marisa-trie` loads a file by its path.
"""

from __future__ import annotations

import atexit
from contextlib import ExitStack
from importlib import resources
from pathlib import Path

_unpacked = ExitStack()
atexit.register(_unpacked.close)

DATA: Path = _unpacked.enter_context(resources.as_file(resources.files("gramoten") / "data"))
PAGE: Path = _unpacked.enter_context(resources.as_file(resources.files("gramoten") / "playground.html"))
