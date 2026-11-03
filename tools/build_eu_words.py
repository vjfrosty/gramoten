"""EU legal Bulgarian the dictionary lacks: дерогация, внедрители, псевдонимизация.

    uv run --no-project --python 3.13 --with marisa-trie==1.4.1 python -I \
        tools/build_eu_words.py EU_JSONL DOWNLOADS

EU_JSONL is one act per line, `{"title": CELEX, "text": …}`, taken from
EUR-Lex (© European Union; reuse allowed, Decision 2011/833/EU), such as
the European Electronic Communications Code (32018L1972), the roaming
regulation (32022R0612), GDPR, the AI Act, the DSA, the DMA, NIS2 and eIDAS.
DOWNLOADS is `build_modern_words.py`'s
folder, whose news and Wikipedia counts guard against typos.

A word is accepted when it is:
- lowercase Cyrillic, 4-30 letters, unknown to the dictionary and the other lists;
- used in two acts, or 5 times in one;
- never seen capitalised only;
- not a likely typo: no known word one edit away is 20 times as frequent in
  the acts, news and Wikipedia, and an added ending is no typo.

The acts are carefully edited, so this is a clean source. Writes
`gramoten/data/eu_words.txt`, read by `spelling.project_words`.
"""

from __future__ import annotations

import collections
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_modern_words import LEIPZIG, leipzig_counts  # noqa: E402

from gramoten import spelling  # noqa: E402

OUT = ROOT / "src" / "gramoten" / "data" / "eu_words.txt"
WORD = re.compile(r"(?<![\w-])[А-Яа-яѝ]{4,30}(?![\w-])")


def main() -> None:
    acts = [json.loads(line) for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if line.strip()]
    (news, _), (wiki, _) = (leipzig_counts(Path(sys.argv[2]), name) for name in LEIPZIG)
    lower: collections.Counter = collections.Counter()
    capital: collections.Counter = collections.Counter()
    in_acts: dict[str, set[str]] = collections.defaultdict(set)
    for act in acts:
        for word in WORD.findall(act["text"]):
            if word.islower():
                lower[word] += 1
                in_acts[word].add(act["title"])
            elif word[:1].isupper() and word[1:].islower():
                capital[word.lower()] += 1
    frequency = lower + news + wiki

    accepted, refused = [], collections.Counter()
    for word, count in lower.items():
        if spelling.is_correct(word):
            continue
        if len(in_acts[word]) < 2 and count < 5:
            continue
        if capital[word] > 5 * count:
            refused["a name"] += 1
            continue
        near = [
            w
            for w in spelling._edits(word)
            if spelling.is_correct(w) and not (word.startswith(w) or w.startswith(word))
        ]
        if any(frequency[w] >= 20 * max(count, 1) for w in near):
            refused["a typo of a frequent word"] += 1
            continue
        accepted.append(word)

    OUT.write_text(
        "# EU legal words the dictionary lacks: built by tools/build_eu_words.py\n"
        + "\n".join(sorted(accepted))
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"{len(acts)} acts; accepted {len(accepted)}; refused {dict(refused)}")
    print("sample:", " ".join(random.Random(3).sample(sorted(accepted), min(120, len(accepted)))))


if __name__ == "__main__":
    main()
