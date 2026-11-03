"""Word counts from the start of the MaCoCu-bg web corpus (CC0), for the word-list builders.

    uv run --no-project --python 3.13 python -I tools/build_web_counts.py ZIP_PART DOWNLOADS [HOLDOUT]

MaCoCu-bg 2.0 (http://hdl.handle.net/11356/1800, CC0, Jožef Stefan Institute et al.)
is one 12 GB zip of Bulgarian web text crawled in 2021. The builders need counts, not
the whole corpus, so ZIP_PART is the zip's first bytes, downloaded with a range request:

    curl -r 0-2999999999 -o macocu_bg_head.zip \
        "https://www.clarin.si/repository/xmlui/bitstream/handle/11356/1800/MaCoCu-bg-2.0.xml.zip?sequence=3&isAllowed=y"

The zip's one member is a deflate stream, so its start decompresses on its own; the
last, cut-off paragraph is dropped. Only text inside <p> is counted; markup, URLs and
attributes are not; nor is a paragraph with a letter Bulgarian does not use (Russian
ы э ё, Serbian ј љ њ ...). Writes DOWNLOADS/macocu_bg_counts.txt: `word count` per line,
lowercase Cyrillic words only.
With HOLDOUT, every 500th paragraph is left out of the counts and written there
instead, one per line: web text the word lists never saw, to measure them on.
"""

from __future__ import annotations

import collections
import re
import struct
import sys
import zlib
from pathlib import Path

#: A whole Cyrillic word; only the all-lowercase ones are counted (`Обама` is not `бама`).
WORD = re.compile(r"(?<![\w-])[А-Яа-яЍѝ]+(?![\w-])")
PARAGRAPH = re.compile(r"<p\b[^>]*>(.*?)</p>", re.S)
TAG = re.compile(r"<[^>]+>")
#: Letters Bulgarian does not use: Russian, Ukrainian, Serbian and Macedonian Cyrillic.
#: The crawl holds some pages in those languages; a paragraph with one is skipped, or
#: their words (`быть`, `сегодня`, `улице`) would count as Bulgarian.
FOREIGN = re.compile("[ыэёЫЭЁіїєґІЇЄҐјљњћђџѓќѕЈЉЊЋЂЏЃЌЅ]")


def paragraphs(zip_part: Path):
    """The text of each complete <p> in the zip member's decompressed start."""
    with zip_part.open("rb") as f:
        header = f.read(30)
        if header[:4] != b"PK\x03\x04":
            raise SystemExit(f"{zip_part}: not the start of a zip file")
        (method,) = struct.unpack("<H", header[8:10])
        name_len, extra_len = struct.unpack("<HH", header[26:30])
        f.read(name_len + extra_len)
        if method != 8:
            raise SystemExit(f"{zip_part}: member is not deflated (method {method})")
        inflate = zlib.decompressobj(-15)
        pending = ""
        while chunk := f.read(1 << 22):
            pending += inflate.decompress(chunk).decode("utf-8", "replace")
            end = pending.rfind("</p>")
            if end < 0:
                continue
            for m in PARAGRAPH.finditer(pending, 0, end + 4):
                yield TAG.sub(" ", m.group(1))
            pending = pending[end + 4 :]


def main() -> None:
    zip_part, downloads = Path(sys.argv[1]), Path(sys.argv[2])
    holdout = Path(sys.argv[3]).open("w", encoding="utf-8") if len(sys.argv) > 3 else None  # noqa: SIM115
    counts: collections.Counter = collections.Counter()
    total = 0
    skipped = 0
    for n, text in enumerate(paragraphs(zip_part)):
        if FOREIGN.search(text):
            skipped += 1
            continue
        if holdout and n % 500 == 0:
            holdout.write(" ".join(text.split()) + "\n")
            continue
        for word in WORD.findall(text):
            if word.islower():  # a capitalised word may be a name
                counts[word] += 1
                total += 1
    out = downloads / "macocu_bg_counts.txt"
    with out.open("w", encoding="utf-8") as f:
        for word, count in counts.most_common():
            f.write(f"{word} {count}\n")
    if holdout:
        holdout.close()
    print(f"{total:,} lowercase words, {len(counts):,} distinct, {skipped:,} foreign paragraphs skipped -> {out}")


if __name__ == "__main__":
    main()
