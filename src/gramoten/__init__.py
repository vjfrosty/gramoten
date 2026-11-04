"""Bulgarian spelling, format and font checks, without a model.

Every result is advice: it never changes text by itself. A `fix` is applied
only when the writer confirms it (or calls `apply_fixes`/`fix_text`); spelling
never carries one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from importlib.metadata import PackageNotFoundError, version

from . import grammar, lexical, messages_bg, mixed_script, orthography, punctuation, spelling, tokenize, typography

try:
    __version__ = version("gramoten")
except PackageNotFoundError:  # run from a source tree that is not installed
    __version__ = "0.0.0"

SPELLING = "spelling"
MIXED_SCRIPT = "mixed_script"

#: The groups of findings: spelling, format, punctuation and grammar. Fonts are elsewhere.
KIND_SPELLING = "spelling"
KIND_FORMAT = "format"
KIND_PUNCTUATION = "punctuation"
#: Grammar and usage: right words in the wrong form (`lexical.py`, `grammar.py`).
KIND_GRAMMAR = "grammar"


@dataclass(frozen=True)
class Issue:
    code: str
    start: int
    end: int
    text: str
    suggestions: tuple[str, ...] = ()
    #: The replacement for text[start:end] when the writer accepts "Fix".
    fix: str | None = None
    #: spelling (red); punctuation, grammar or format (blue).
    kind: str = field(default=KIND_FORMAT)
    message: str = ""
    #: Counted in the panel and applied by "Fix all", never underlined.
    quiet: bool = False
    #: `message` in Bulgarian (`messages_bg`); filled in by `check`.
    message_bg: str = ""

    def to_json(self) -> dict:
        return {
            "code": self.code,
            "kind": self.kind,
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "suggestions": list(self.suggestions),
            "fix": self.fix,
            "message": self.message,
            "message_bg": self.message_bg or messages_bg.bulgarian(self.message),
            "quiet": self.quiet,
        }


#: How many unknown words of one call get the two-edit suggestion search (5-15 ms a
#: word); the rest get one-edit and sound-alike suggestions. A count, not a time, so the
#: same text always gets the same suggestions.
DEEP_SUGGESTIONS_PER_CALL = 20


def check(text: str, extra: frozenset[str] = frozenset(), _deep: list[int] | None = None) -> list[Issue]:
    """Spelling, format and punctuation of one text, ordered by position."""
    found = check_spelling(text, extra, _deep)
    found += [
        Issue(
            h.code,
            h.start,
            h.end,
            text[h.start : h.end],
            tuple(x for x in (h.fix, h.suggestion) if x is not None),
            h.fix,
            KIND_FORMAT,
            h.message,
            h.code in typography.QUIET,
        )
        for h in typography.check(text)
    ]
    found += [
        Issue(
            h.code, h.start, h.end, text[h.start : h.end], (h.fix,) if h.fix else (), h.fix, KIND_PUNCTUATION, h.message
        )
        for h in punctuation.check(text)
    ]
    found += [_grammar(text, h) for h in lexical.check(text)]
    found += [_grammar(text, h) for h in grammar.check(text)]
    found += [
        Issue(
            h.code,
            h.start,
            h.end,
            text[h.start : h.end],
            (h.fix,) if h.fix else (),
            h.fix,
            KIND_GRAMMAR if h.code == "pronoun_i" else KIND_FORMAT,
            h.message,
        )
        for h in orthography.check(text)
    ]
    found = [replace(i, message_bg=messages_bg.bulgarian(i.message)) for i in found]
    return sorted(found, key=lambda i: (i.start, i.end, i.code))


def apply_fixes(text: str, issues: list[Issue], codes: frozenset[str] | set[str] | None = None) -> str:
    """`text` with the fix of every issue that carries one applied.

    `codes`, when given, limits it to issues with those codes. Issues whose span no
    longer holds their `text` (the text changed since the check) are skipped, and of
    two overlapping issues only the one that starts first is applied. Spelling has no
    fix, so it is never changed. Check again afterwards: a fix can reveal another finding.
    """
    chosen: list[tuple[Issue, str]] = []
    end = -1
    for i in sorted(issues, key=lambda i: (i.start, i.end)):
        if i.fix is None or (codes is not None and i.code not in codes):
            continue
        if text[i.start : i.end] != i.text or i.start < end:
            continue
        chosen.append((i, i.fix))
        end = i.end
    for i, fix in reversed(chosen):
        text = text[: i.start] + fix + text[i.end :]
    return text


#: How many check-and-fix rounds `fix_text` runs at most.
FIX_ROUNDS = 5


def fix_text(text: str, extra: frozenset[str] = frozenset(), codes: frozenset[str] | set[str] | None = None) -> str:
    """`text` with every certain fix applied, checking again until nothing changes.

    One `apply_fixes` pass skips an issue that overlaps another (a double space inside
    ` - `); the next round's check finds it again. Spelling is never changed.
    """
    for _ in range(FIX_ROUNDS):
        fixed = apply_fixes(text, check(text, extra), codes)
        if fixed == text:
            break
        text = fixed
    return text


def _grammar(text: str, h: lexical.Hit) -> Issue:
    return Issue(
        h.code, h.start, h.end, text[h.start : h.end], (h.fix,) if h.fix else (), h.fix, KIND_GRAMMAR, h.message
    )


def check_many(texts: list[str], extra: frozenset[str] = frozenset()) -> list[list[Issue]]:
    """`check` of each text. Every rule reads one text alone; the batch is a convenience."""
    deep = [DEEP_SUGGESTIONS_PER_CALL]
    return [check(text, extra, deep) for text in texts]


def _take(left: list[int]) -> bool:
    """Whether one more word may have the two-edit search, counting it."""
    if left[0] <= 0:
        return False
    left[0] -= 1
    return True


def _sentence_start(text: str, start: int) -> bool:
    """Nothing but punctuation, an opening quote or a line break before `start`."""
    return re.search(r"(^|[.!?…:;]\s*|[„\"«(]\s*|\n\s*|^\W*)$", tokenize.before(text, start)) is not None


def check_spelling(text: str, extra: frozenset[str] = frozenset(), _deep: list[int] | None = None) -> list[Issue]:
    """Mixed-script words first (they are not misspellings), then unknown words."""
    deep = _deep if _deep is not None else [DEEP_SUGGESTIONS_PER_CALL]
    found: list[Issue] = []
    for word in tokenize.words(text):
        if word.mixed_script:
            fixed = mixed_script.fix(word.text)
            found.append(
                Issue(
                    MIXED_SCRIPT,
                    word.start,
                    word.end,
                    word.text,
                    (fixed,) if fixed else (),
                    fixed,
                    KIND_FORMAT,
                    "Latin and Cyrillic letters mixed in one word",
                )
            )
        elif word.clean[:1].isupper() and not word.clean.isupper() and not _sentence_start(text, word.start):
            # A capital inside a sentence is a name, almost never a typo.
            continue
        elif (
            spelling.is_name(word.clean)
            or word.clean.lower() in spelling.UNITS
            or (word.clean.lower() in spelling.ABBREVIATIONS and text[word.end : word.end + 1] == ".")
        ):
            continue
        elif not spelling.is_correct(word.clean, extra):
            found.append(
                Issue(
                    SPELLING,
                    word.start,
                    word.end,
                    word.text,
                    tuple(spelling.suggest(word.clean, extra=extra, deep=_take(deep))),
                    None,
                    KIND_SPELLING,
                    "Not in the dictionary",
                )
            )
    return found
