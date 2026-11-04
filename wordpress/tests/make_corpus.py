"""The expected results for the TypeScript port, from the Python package itself.

    uv run --group dev python wordpress/tests/make_corpus.py

Writes `wordpress/tests/corpus.json`: every Cyrillic string in the Python tests, the project's
Bulgarian documents, and seeded mutations of them (typos, stray spaces, emoji, lookalike
letters, invisible characters), each with what `gramoten.check` and `gramoten.fix_text` say.
Offsets are turned into UTF-16 units, which is what JavaScript and the block editor count.
"""

from __future__ import annotations

import ast
import json
import os
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import gramoten  # noqa: E402

OUT = Path(__file__).with_name("corpus.json")
CYRILLIC = re.compile(r"[а-яА-Я]")
SEED = 20261104
#: Raise it for a longer hunt: `CORPUS_MUTATIONS=30`.
MUTATIONS_PER_TEXT = int(os.environ.get("CORPUS_MUTATIONS", 3))
#: Keeps the run short: a text this long is cut into pieces of about this size.
PIECE = 1500

#: Rules the Python tests' strings do not reach on their own.
SEEDS = [
    "Нито той дойде нито тя се обади.",
    "Каза, че: нито яде нито пие.",
    "нито едно нито друго",
]
INSERTS = [
    " ",
    "  ",
    " ",
    "😀",
    "𝐀",
    "­",
    "́",
    "​",
    "\n",
    "\r\n",
    ",",
    ",,",
    " - ",
    "...",
    '"',
    "„",
    "(",
    ")",
    "%%name%%",
    "{P:first_name}",
    "www.example.bg",
    "a@b.bg",
    "5",
    "10 лв.",
    "EUR 5",
    "٣",
    "²",
    "и и ",
]
LOOKALIKE = str.maketrans("аеорсх", "aeopcx")


def strings() -> list[str]:
    found: list[str] = []
    for path in sorted((ROOT / "tests").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and CYRILLIC.search(node.value):
                found.append(node.value)
    for name in ("README.md", "CHANGELOG.md", "HANDOFF.md", "src/gramoten/README.md"):
        path = ROOT / name
        if path.exists():
            found += [p for p in re.split(r"\n\s*\n", path.read_text(encoding="utf-8")) if CYRILLIC.search(p)]
    found += SEEDS
    # Real text, when it is on this machine: `CORPUS_PROSE=tools/dl/eval/web_holdout.txt`.
    prose = os.environ.get("CORPUS_PROSE")
    if prose:
        lines = [line for line in Path(prose).read_text(encoding="utf-8").splitlines() if CYRILLIC.search(line)]
        found += random.Random(SEED).sample(lines, min(int(os.environ.get("CORPUS_PROSE_LINES", 5000)), len(lines)))
    pieces: list[str] = []
    for text in found:
        pieces += [text[i : i + PIECE] for i in range(0, len(text), PIECE)]
    return sorted(set(pieces))


def mutate(text: str, rng: random.Random) -> str:
    chars = list(text)
    for _ in range(rng.randint(1, 4)):
        at = rng.randrange(len(chars) + 1)
        kind = rng.randrange(6)
        if kind == 0:
            chars[at:at] = list(rng.choice(INSERTS))
        elif kind == 1 and at < len(chars):
            del chars[at]
        elif kind == 2 and at + 1 < len(chars):
            chars[at], chars[at + 1] = chars[at + 1], chars[at]
        elif kind == 3 and at < len(chars):
            chars[at] = chars[at].translate(LOOKALIKE)
        elif kind == 4 and at < len(chars):
            chars[at] = rng.choice("абвгдежзийклмнопрстуфхцчшщъьюя")
        elif kind == 5 and at < len(chars):
            chars[at] = chars[at].swapcase()
    return "".join(chars)


def units(text: str, offset: int) -> int:
    return len(text[:offset].encode("utf-16-le")) // 2


def entry(text: str, extra: frozenset[str]) -> dict:
    issues = []
    for issue in gramoten.check(text, extra):
        found = issue.to_json()
        found["start"], found["end"] = units(text, issue.start), units(text, issue.end)
        issues.append(found)
    return {"text": text, "extra": sorted(extra), "issues": issues, "fixed": gramoten.fix_text(text, extra)}


def main() -> None:
    rng = random.Random(SEED)
    originals = strings()
    texts = list(originals)
    for text in originals:
        texts += [mutate(text, rng) for _ in range(MUTATIONS_PER_TEXT)]
    texts = sorted(set(texts))

    corpus = [entry(text, frozenset()) for text in texts]
    # The added words count too: each word flagged in some texts, added for that text.
    for item in rng.sample(corpus, min(300, len(corpus))):
        flagged = [i["text"].lower() for i in item["issues"] if i["kind"] == "spelling"]
        if flagged:
            corpus.append(entry(item["text"], frozenset(flagged[:2])))

    OUT.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    print(f"{len(corpus)} texts, {sum(len(c['issues']) for c in corpus)} findings -> {OUT}")


if __name__ == "__main__":
    main()
