"""The words people add to the dictionary: names, brands, new vocabulary.

Who may add words is the host app's decision (it enforces who calls `add` and
`remove`). The words sit in one JSON file, `{"words": {word: {"by": user, "at": iso time}}}`, replaced
atomically on every change, so a crash leaves the old file or the new one and
never half of either. They are checked as `extra=` by `gramoten.check`.

A word is accepted only if it can be a word: Cyrillic letters, optionally
joined by one hyphen (`е-Тикет`), 2-40 characters, lowercased on the way in. A
word the dictionary already knows is accepted and not stored.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from . import spelling

#: A shared list, not a corpus: past this, adding is refused.
MAX_WORDS = 5000

_WORD = re.compile(r"[а-яѝ]+(?:-[а-яѝ]+)?")


class WordError(ValueError):
    """A word that cannot be added, with the sentence that says why."""


def normalise(word: str) -> str:
    candidate = word.strip().lower()
    if not 2 <= len(candidate) <= 40 or not _WORD.fullmatch(candidate):
        raise WordError("A word is 2 to 40 Cyrillic letters, with at most one hyphen.")
    return candidate


def load_words(path: str | Path) -> frozenset[str]:
    """An app's own words, to pass as `extra=`: the names, brands and places its texts use,
    which do not belong in the shared package (`Кукушев ще води.` at a sentence start).

    A `.json` file is read as a `WordStore` file; any other as plain UTF-8 text, one word
    per line, `#` starting a comment. Words are lowercased; nothing is checked or refused."""
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        return frozenset(w.lower() for w in json.loads(text).get("words", {}))
    lines = (line.split("#", 1)[0].strip().lower() for line in text.splitlines())
    return frozenset(line for line in lines if line)


class WordStore:
    """The added words in one JSON file; safe for the threads of one process."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = Lock()

    def _read(self) -> dict[str, dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        words = data.get("words", {}) if isinstance(data, dict) else {}
        return words if isinstance(words, dict) else {}

    def _write(self, words: dict[str, dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".words-", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                json.dump({"words": dict(sorted(words.items()))}, out, ensure_ascii=False, indent=1)
            os.replace(temporary, self.path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def words(self) -> frozenset[str]:
        return frozenset(self._read())

    def entries(self) -> list[dict]:
        """`[{word, by, at}]`, alphabetical."""
        return [{"word": w, **meta} for w, meta in sorted(self._read().items())]

    def add(self, word: str, by: str) -> bool:
        """True when the word is now in the list because of this call."""
        word = normalise(word)
        if spelling.is_correct(word):
            return False
        with self._lock:
            words = self._read()
            if word in words:
                return False
            if len(words) >= MAX_WORDS:
                raise WordError(f"The dictionary holds {MAX_WORDS} added words; remove some first.")
            words[word] = {"by": by, "at": datetime.now(UTC).isoformat(timespec="seconds")}
            self._write(words)
            return True

    def remove(self, word: str) -> bool:
        """True when the word was in the list."""
        word = word.strip().lower()
        with self._lock:
            words = self._read()
            if words.pop(word, None) is None:
                return False
            self._write(words)
            return True
