"""Expand the bg_BG Hunspell dictionary into every word form, as a marisa trie.

    uv run --no-project --python 3.13 --with spylls==0.1.7 --with marisa-trie==1.4.1 \
        --with psutil python -I tools/build_bg_forms.py

gramoten checks Bulgarian spelling against a trie of word forms rather than a
Hunspell engine: the trie is small and answers in microseconds.

The affix rules are applied here, once. Each candidate is then kept only when
spylls itself accepts it, so the trie holds exactly the forms Hunspell would
accept, lowercased. Candidates are filtered across a process pool at
BelowNormal priority.
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
DICT = HERE / "bg_BG" / "bg_BG"
OUT = HERE.parent / "src" / "gramoten" / "data" / "bg_forms.marisa"

_DICT = None


def _init() -> None:
    global _DICT
    import psutil

    proc = psutil.Process()
    proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if sys.platform == "win32" else 10)
    from spylls.hunspell import Dictionary

    _DICT = Dictionary.from_files(str(DICT))


def _accepted(words: list[str]) -> list[str]:
    return [w for w in words if _DICT.lookup(w)]


def candidates(dictionary) -> set[str]:
    """Stems plus every suffixed form (the .aff has 26 suffix sets, no prefixes or compounds)."""
    aff = dictionary.aff
    assert not aff.PFX and not aff.COMPOUNDFLAG, "the expander handles suffixes only"
    out: set[str] = set()
    for word in dictionary.dic.words:
        out.add(word.stem)
        for flag in word.flags:
            for sfx in aff.SFX.get(flag, ()):
                if word.stem.endswith(sfx.strip) and sfx.cond_regexp.search(word.stem):
                    base = word.stem[: len(word.stem) - len(sfx.strip)] if sfx.strip else word.stem
                    out.add(base + sfx.add)
    return out


def main() -> None:
    import marisa_trie
    from spylls.hunspell import Dictionary

    started = time.perf_counter()
    forms = sorted(candidates(Dictionary.from_files(str(DICT))))
    workers = max(1, min(20, (os.cpu_count() or 4) - 2))
    parts = [forms[i::200] for i in range(200)]
    with ProcessPoolExecutor(workers, initializer=_init) as pool:
        valid = {w.lower() for chunk in pool.map(_accepted, parts) for w in chunk}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    marisa_trie.Trie(sorted(valid)).save(str(OUT))
    print(
        f"{len(forms)} candidates -> {len(valid)} forms in {time.perf_counter() - started:.0f}s "
        f"({workers} workers) -> {OUT} ({OUT.stat().st_size / 2**20:.1f} MB)"
    )


if __name__ == "__main__":
    main()
