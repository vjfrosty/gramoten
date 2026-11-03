"""Shared by the tests: real typos and short views of the findings."""

from __future__ import annotations

from pathlib import Path

import gramoten

ROOT = Path(__file__).resolve().parents[1]

#: Real typos, and the word the suggestion list must contain.
SENT_TYPOS = {
    "консулатант": "консултант",
    "инфрастурктура": "инфраструктура",
    "пределожения": "предложения",
    "интрнет": "интернет",
    "професионалсти": "професионалисти",
    "удовоствието": "удоволствието",
    "услигите": "услугите",
    "категоария": "категория",
}


def codes(text: str) -> list[tuple[str, str]]:
    return [(i.code, i.text) for i in gramoten.check_spelling(text)]


def fixes(text: str, kind: str) -> list[tuple[str, str, str | None]]:
    return [(i.code, i.text, i.fix) for i in gramoten.check(text) if i.kind == kind]
