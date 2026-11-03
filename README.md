<p align="center"><img src="https://raw.githubusercontent.com/vjfrosty/gramoten/main/assets/logo-long.png" alt="Грамотен" width="480"></p>

# gramoten (Грамотен)

Bulgarian spelling, punctuation, grammar and format checks for any Bulgarian text, by rule, with no language model and no network. It finds problems and proposes fixes; it never changes text by itself.

```python
import gramoten

for issue in gramoten.check("Знаем че 5-ти май е 19 годишен празник  - до сега."):
    print(issue.kind, issue.code, repr(issue.text), "->", issue.fix, issue.message_bg)

gramoten.fix_text("Знаем че до сега.")   # 'Знаем, че досега.': every certain fix, never spelling
```

## Goal

gramoten is meant to be a quick, free Bulgarian spell checker that any app can build in. In practice that means:

- **Quick.** A 300-word e-mail is checked in about 12 ms, and the word lists load once in about 15 ms. That is fast enough to check text as the user types, or to check every message a server sends.
- **Free of cost.** The code is MIT and the word lists come from open sources (see Licence). There is no API key, no per-word fee, no account and no usage limit.
- **Offline and private.** Everything runs in the same process, with no network calls and no language model. The text never leaves the machine, and results are the same on every run and every machine.
- **Small.** The only dependency is `marisa-trie`. The wheel is about 9 MB with every word list, and a process with everything loaded takes about 37 MB of RAM.
- **Catches words written as they sound.** Many Bulgarian misspellings come from writing a word the way it is pronounced (`подтискам` for `потискам`, `до сега` for `досега`). The 386,241 known misspellings and gramoten's own corrections catch these and suggest the right form first. Suggestions for other unknown words are ranked by how often each word is used.
- **Safe.** It reports problems and proposes fixes. The app or the user decides what to apply, and spelling is never changed automatically.

It is not a style editor and does not rewrite sentences. It finds what can be decided by rule and leaves the rest alone.

## Install

Python 3.11 or newer. The only dependency is `marisa-trie`, which has wheels for Windows, macOS and Linux.

```bash
pip install gramoten-0.1.0-py3-none-any.whl     # a built wheel (uv build, or the CI artifact)
pip install git+https://github.com/OWNER/gramoten   # straight from the repository
pip install -e .                                 # from a checkout, for development
```

Once it is on PyPI: `pip install gramoten` (or `uv add gramoten`). The wheel holds the word lists (about 9 MB); nothing is downloaded at run time.

## Use it in an app

The short version: call `gramoten.check(text)` and show the findings; apply the ones the user accepts with `gramoten.apply_fixes`. The full guide, with a web endpoint, the JSON shape, offsets in JavaScript, your own words and threads, is "Integrating" in `src/gramoten/README.md`.

## Command line

```bash
python -m gramoten text.txt          # findings with line and column; exit 1 when something is found
python -m gramoten --fix text.txt    # the corrected text
python -m gramoten serve             # a test page on http://localhost:8765
```

The full reference (every rule, its fix, how it was measured) is `src/gramoten/README.md`, in the source and in the installed package (`gramoten/README.md`).

## What works

| Check | What it does |
|---|---|
| Spelling | Flags unknown words and suggests up to five, most used first. Never auto-fixes. |
| Punctuation | Commas before conjunctions and relative words, after a vocative, inside compounds such as `въпреки, че`; doubled marks, unbalanced brackets and quotes. |
| Grammar | Double article, article after a preposition or a copula, count forms (`24 месеци`), `в/във`, `с/със`, agreement with `Вие`, repeated words. |
| Orthography | `й` → `ѝ`, ordinals (`5-ти` → `5-и`), dates, `19-годишен`, `10-процентна`, `г-н` without a full stop, words written together (`досега`). |
| Format | Dashes, Bulgarian quotation marks, spaces, ellipsis, decimal comma, the euro sign; prices in leva are flagged, with no conversion. |
| Mixed script | Latin letters inside a Cyrillic word and the reverse (`пoлучавате`, `ВMW`). |
| Fonts | Fonts that never load, Office leaks, missing fallbacks, name variants, `<font>` tags, fonts outside the template's own. |

**Word lists:**
- the bgOffice dictionary, 866,654 forms (MPL-1.1), and a morphology built from it;
- 46,888 modern words from news, Wikipedia and 675M words of web text, about 2,900 more read word by word, and 49,978 of their other forms made with the dictionary's paradigms;
- telecom terms, 1,171 forms of address, EU legal words, and 7,870 names (with every Bulgarian settlement, from the EKATTE register);
- 386,241 searched misspellings with their corrections;
- gramoten's own corrections for misspellings the other lists miss.

**Measured (2026-11-03):** spelling flags per 1,000 words on text the word lists never saw. A flag is not always a false alarm: real typos are counted too.

| Text | Flags per 1,000 words |
|---|---|
| Web text (MaCoCu-bg, 7,757 held-out paragraphs, 325,321 words) | 7.17 |
| News (Leipzig 2022, 10,000 sentences, 173,644 words) | 5.91 |
| bg.wikipedia (34 random articles, 17,535 words) | 13.97 |

What is flagged is mostly rare words, dialect and slang (`абе`, `нема`), old spelling (`казватъ`), abbreviations with no full stop (`изм`, `авг`) and names at a sentence start. A name an app's texts use goes in that app's own word list (`--words FILE`), not in the package.

Speed is about 0.17 M characters a second on news text, so a 300-word e-mail takes about 12 ms. A process with the package and every list loaded takes about 37 MB of RAM; loading the lists takes about 15 ms, once.

## Layout

| Folder | Holds |
|---|---|
| `src/gramoten/` | The package: code, its word lists (`data/`, 14 MB) and the full reference README. |
| `tests/` | The tests, one file per area: spelling, format, punctuation, grammar, fonts and the API. |
| `tools/` | The scripts that rebuild the word lists from their sources, and the sources' licences (`tools/bg_BG/SOURCE.md`). |

## Build and test

```bash
uv run --group dev pytest -q          # tests
uv run --group dev ruff check src tests tools
uv run --group dev mypy               # types
uv build                              # wheel and sdist in dist/
```

CI (`.github/workflows/ci.yml`) runs the same on Linux, macOS and Windows, Python 3.11 to 3.13. Changes are listed in `CHANGELOG.md`.

It depends on `marisa-trie` only and needs Python 3.11 or newer.

## Licence

| Part | Licence |
|---|---|
| Code and gramoten's own lists | MIT, © 2026 Yasen Ivanov (`LICENSE`) |
| Spelling dictionary, morphology and lists built with them | MPL-1.1, from bgOffice's GPL/LGPL/MPL dictionary |
| Misspelling table | MIT, from Chitanka |
| Word counts behind modern words, names and ranking | CC BY, Leipzig Corpora Collection |
| EU legal words | © European Union, Decision 2011/833/EU |

Credits: `NOTICE`; sources: `tools/bg_BG/SOURCE.md`, `tools/morphology/SOURCE.md`. `pyproject.toml` declares `MIT AND MPL-1.1 AND LicenseRef-Leipzig-CC-BY`.
