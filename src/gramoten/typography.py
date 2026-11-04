"""Bulgarian typography: spaces, dashes, quotes, ellipses, prices.

Every rule here has one certain correction, offered as a fix the writer
confirms.

Nothing inside a protected range (`%%…%%`, AMPscript, URLs, e-mail addresses)
is read: `www.example.bg` is not a missing space after a full stop.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .tokenize import protected_ranges

NBSP = "\u00a0"
CURRENCY = r"(?:лв\.?|лева|€|евро|EUR|BGN)"
#: Right, but on nearly every price: an underline under each would hide the findings that matter.
QUIET = frozenset({"nbsp_number_unit"})
#: Units a number must not be separated from at a line end.
UNITS = CURRENCY + r"|%|GB|MB|TB|Mbps|Gbps|Mb/s|Gb/s|ГБ|МБ|мин\.?|мес\.?|г\.|бр\.|SMS|MMS"


@dataclass(frozen=True)
class Hit:
    code: str
    start: int
    end: int
    message: str
    #: None: the finding has no certain correction, only `suggestion`.
    fix: str | None
    suggestion: str | None = None


def _rules(text: str):
    # Bulgaria pays in euro since 2026-01-01: a price in leva is a finding with no
    # amount offered, since a converted price is the writer's to set, not a rule's.
    for m in re.finditer(
        r"(?<![\w.,])(\d{1,3}(?:[ \u00a0]\d{3})+|\d+)(?:[.,](\d{1,2}))?[ \u00a0]?(лв\.?|лева|BGN)(?![^\W\d_])", text
    ):
        yield Hit("currency_bgn", m.start(), m.end(), "A price in leva: prices are in euro", None)
    for m in re.finditer(r"(?<![\w.,])(€|EUR)[ \u00a0]?(\d+(?:[ \u00a0]\d{3})*(?:[.,]\d{1,2})?)(?!\d)", text):
        yield Hit(
            "euro_symbol_position",
            m.start(),
            m.end(),
            "In Bulgarian the € sign goes after the amount",
            f"{m.group(2).strip().replace('.', ',')}\u00a0€",
        )
    for m in re.finditer(r"(?<=\S)( {2,})(?=\S)", text):
        yield Hit("double_space", m.start(1), m.end(1), "More than one space", " ")
    for m in re.finditer(r"(?<=[^\W\d_])( +)([,.!?;:])(?=\s|$)", text):
        yield Hit("space_before_punctuation", m.start(1), m.end(2), "A space before the punctuation mark", m.group(2))
    for m in re.finditer(r"(?<=[А-Яа-я])([,;:!?])(?=[А-Яа-я])", text):
        yield Hit(
            "space_after_punctuation", m.start(1), m.end(1), "No space after the punctuation mark", m.group(1) + " "
        )
    for m in re.finditer(r"(?<=[^\W\d_]) - (?=[^\W\d_])", text):
        yield Hit("dash", m.start(), m.end(), "A hyphen used as a dash", " – ")
    for m in re.finditer(r"(?<![\w\"])\"([^\"\n]{1,200}?)\"(?![\w\"])", text):
        yield Hit("quotes", m.start(), m.end(), "Bulgarian quotation marks are „…“", f"„{m.group(1)}“")
    for m in re.finditer(r"(?<!\.)\.\.\.(?!\.)", text):
        yield Hit("ellipsis", m.start(), m.end(), "Three dots are one character: …", "…")
    for m in re.finditer(r"(?<![\d.,])(\d{1,6})\.(\d{2})(?=\s*" + CURRENCY + r")", text):
        yield Hit(
            "decimal_separator", m.start(), m.end(), "A price takes a decimal comma", f"{m.group(1)},{m.group(2)}"
        )
    # 02 октомври -> 2 октомври: a day written before the month takes no leading zero
    for m in re.finditer(
        r"(?<![\w.,])0([1-9]) (януари|февруари|март|април|май|юни|юли|август|септември|"
        r"октомври|ноември|декември)(?![^\W\d_])",
        text,
        flags=re.I,
    ):
        yield Hit(
            "date_leading_zero", m.start(), m.start() + 2, "A day before the month has no leading zero", m.group(1)
        )
    # 1990г. -> 1990 г.: an abbreviation after a number is a word of its own
    # `20 000г.`: the end of a number with a thousands space is no year, so it is left.
    for m in re.finditer(r"(?<![\w.,])(?<!\d[  ])(\d{1,4})(г|в|хил|млн|млрд)\.(?=\s|$|[,;:)–—-])", text):
        yield Hit(
            "abbreviation_space",
            m.start(),
            m.end(),
            "A space between the number and the abbreviation",
            f"{m.group(1)} {m.group(2)}.",
        )
    # 31.12.2024г. -> 31.12.2024 г.: the year of a full date.
    for m in re.finditer(r"(?<![\w.,])\d{1,2}\.\d{1,2}\.(\d{4})(г)\.(?=\s|$|[,;:)–—-])", text):
        yield Hit(
            "abbreviation_space",
            m.start(1),
            m.end(),
            "A space between the number and the abbreviation",
            f"{m.group(1)} {m.group(2)}.",
        )
    for m in re.finditer(r"(?<![\w.,])(\d[\d,]*) (" + UNITS + r")(?![^\W\d_])", text):
        yield Hit(
            "nbsp_number_unit",
            m.end(1),
            m.end(1) + 1,
            "Keep the number and its unit on one line (non-breaking space)",
            NBSP,
        )


def check(text: str) -> list[Hit]:
    ranges = protected_ranges(text)
    return [hit for hit in _rules(text) if not any(hit.start < end and start < hit.end for start, end in ranges)]
