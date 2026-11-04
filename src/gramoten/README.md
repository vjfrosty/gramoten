<img src="../../assets/logo-short-128.png" alt="Грамотен" width="64" align="right">

# gramoten: Bulgarian spelling, punctuation and format, without a model

`gramoten` (Грамотен) reads Bulgarian text and returns findings: words the dictionary does not know, missing or wrong commas, and format problems such as dashes, quotation marks, spaces and prices. Every finding has exact offsets. Where the correction is certain, it also carries that correction.

- **No model, no network.** It runs entirely on rules and a word list.
- **A package of its own.** It needs one library, `marisa-trie`. The repository root builds it into a wheel; `tools/` holds the scripts that build its word lists.
- **Advice only.** It never changes text by itself; the host decides what to show and what to apply.

## Use

```python
import gramoten

for issue in gramoten.check('Знаем че обичате смартфони  - вижте "Плати онлайн".'):
    print(issue.kind, issue.code, repr(issue.text), "->", repr(issue.fix), issue.message)
# punctuation comma_before_conjunction ' че' -> ', че' Comma before „че“
# format double_space '  ' -> ' ' More than one space
# format quotes '"Плати онлайн"' -> '„Плати онлайн“' Bulgarian quotation marks are „…“
```

The hyphen used as a dash (` - `) is found once the double space before it is fixed: `fix_text` checks again until nothing changes.

`check(text, extra=frozenset())` checks one text. `check_many(texts, extra)` checks several; every rule reads one text alone. `extra` is the set of added words (see "Added words"). It returns a list of `Issue`, ordered by position:

| Field | Meaning |
|---|---|
| `code` | The rule, e.g. `spelling`, `comma_before_conjunction`, `dash` (table below). |
| `kind` | `spelling` (show red); `punctuation`, `grammar` or `format` (show blue). |
| `start`, `end`, `text` | `text == input[start:end]`; offsets are Python string indices. |
| `fix` | What replaces `text` on "Fix", or `None`. **Spelling never has one.** |
| `suggestions` | For spelling, up to five known words, closest first (sound-alike changes count as half an edit), common words before rare ones. Otherwise the fix. |
| `message` | One English sentence for the writer. |
| `message_bg` | The same sentence in Bulgarian (`messages_bg.py`). |
| `quiet` | Right, but too frequent to underline. Count it and let "Fix all" apply it. |

`Issue.to_json()` gives the same fields as a dict. This is the HTTP shape the frontend reads.

**Applying fixes.**
- `apply_fixes(text, issues, codes=None)` applies, in one pass, the fix of every issue that has one. With `codes` it applies only those rules. It skips an issue whose span no longer holds its `text`, and of two overlapping issues it applies only the first.
- `fix_text(text, extra=frozenset(), codes=None)` checks and applies again until nothing changes (at most five rounds). One pass is not always enough: a double space inside ` - ` hides the dash until the next check.
- Neither ever changes spelling.

```python
gramoten.fix_text("Знаем че 5-ти май е 19 годишен празник  - до сега.")
# 'Знаем, че 5 май е 19-годишен празник – досега.'
```

**Bulgarian messages.** `messages_bg.py` holds one entry per rule message: the English text as a pattern and its Bulgarian wording. A message with no entry stays in English. A test reads every rule's source and fails when a message has no entry, so add the entry together with a new rule.

## Command line

```bash
python -m gramoten FILE ...            # or: gramoten FILE ..., once the package is installed
cat text.txt | python -m gramoten      # standard input
python -m gramoten --fix FILE          # the text with every certain fix applied (fix_text)
python -m gramoten --json FILE         # the findings as JSON
python -m gramoten serve               # the test page on http://localhost:8765
```

`check` (the default command) prints one line per finding as `file:line:column: kind code: „text“ – message → fix or suggestions`. Spaces show as `⍽` and line breaks as `↵`. It exits 0 when nothing is found, 1 when something is and 2 on an error, so it fits scripts, pre-commit hooks and CI.

| Option | Does |
|---|---|
| `--lang en` | English messages (default `bg`). |
| `--extra WORDS` | Comma-separated words to accept as correct. |
| `--words FILE` | Your own words to accept, such as the names and brands your texts use: one per line (`#` starts a comment), or a `WordStore` `.json`. Repeatable. |
| `--all` | Also show quiet findings (non-breaking spaces). |
| `--fix` | Print the fixed text instead of the findings; one input only. |

Files are read as UTF-8.

## Test page (`server.py`, `playground.html`)

`python -m gramoten serve [--port 8765] [--host 127.0.0.1] [--open]` serves a page for trying the checker by hand. It uses only the standard library.
- **Underlines:** findings are underlined as you type, red for spelling and blue for the rest.
- **Popup:** clicking an underline shows the Bulgarian message and the corrections; clicking a correction applies it. **Игнорирай** hides the finding, and **Добави в речника** accepts the word for this page.
- **Поправи всички:** applies `fix_text`.
- **Table:** every finding is also listed in a table.

Its routes are `POST /check` (`{text, extra}` → `{ms, issues}`) and `POST /fix` (`{text, extra}` → `{text}`). It listens on this computer only by default and is for testing, not for serving others.

## What is never read

Text inside these is protected and never checked or changed (`tokenize.PROTECTED`):
- `%%…%%` personalisation strings;
- AMPscript: `%%[ … ]%%` and `%%= … =%%`;
- URLs;
- e-mail addresses.

Words with digits (`5G`, `S10`) and all-Latin words (`Netflix`) are not spelt, and all-capital words up to five letters are taken as acronyms (`ДДС`). A host with code inside its words, such as an editor chip, sends it as one `◊` (`CHIP`), which keeps every rule quiet around it.

## The rules

| Module | Codes | Fix |
|---|---|---|
| `spelling.py` | `spelling` | never; `suggestions` only |
| `mixed_script.py` | `mixed_script`: Latin letters inside a Cyrillic word (`пoлучавате`) or the reverse (`ВMW`) | yes, when every letter has a lookalike and one script is the majority |
| `typography.py` | `double_space`, `space_before_punctuation`, `space_after_punctuation`, `dash`, `quotes`, `ellipsis`, `decimal_separator`, `abbreviation_space` (`1990г.`, `31.12.2024г.`), `date_leading_zero` (`02 октомври`), `euro_symbol_position` | yes |
| `typography.py` | `nbsp_number_unit` (quiet) | yes |
| `typography.py` | `currency_bgn`: a price in лв/лева/BGN, since Bulgaria pays in euro from 2026-01-01 | **no**, and no amount is ever offered: the price is the writer's to set |
| `punctuation.py` | `comma_before_conjunction`, `comma_before_relative`, `comma_repeated_conjunction`, `comma_vocative`, `comma_inside_compound` | yes, where certain |
| `punctuation.py` | `double_punctuation`, `unbalanced_bracket`, `unbalanced_quote` | no |
| `lexical.py` (kind `grammar`) | `article_after_preposition` (`от сумарният`), `v_vav`/`s_sas` (`с свободни`), `written_together` (`до сега`, `от тук`, `до колко е`, `тъмно зелен`, `научно-изследователски`), `superlative_hyphen` (`най много`), `number_range` (`10-12`), `repeated_word` (`и и`, fix deletes) | yes |
| `orthography.py` | `pronoun_i` (`й` → `ѝ`), `ordinal_suffix` (`5-ти` → `5-и`, `1-и` → `1-ви`, `7-ма` → `7-а`, `14-ят` → `14-ият`), `ordinal_date` (`9-ти март` → `9 март`), `ordinal_roman` (`XXI-ви` → `XXI`), `number_adjective` (`19 годишен` → `19-годишен`), `percent_adjective` (`10%-на` → `10-процентна`), `title_period` (`г-н.` → `г-н`) | yes |
| `grammar.py` (kind `grammar`, needs `morphology.py`) | `double_article` (`Вашите данните`), `article_after_copula` (`е най-добрия`), `count_form` (`24 месеци`), `plural_after_dvama` (`трима сина`), `vie_agreement` (`Вие държи`) | yes, when one form fits |

**How the punctuation rules were chosen.** Each rule was measured before it shipped:
- on 471 marketing e-mails (a private set, not included);
- by reading every hit on 60 bg.wikipedia articles;
- by deleting the corpus's own correct commas, to measure recall;
- against hand-written tricky sentences.

Only precise rules ship. The measured precision is in the docstrings of `punctuation.py` and `lexical.py`, with the rules left out and why. The grammar rules were also read on 22,089 model-written strings and 29 edited books; most samples are under 30 hits.

**Sources:** the official orthographic dictionary (ОПР 2012), the Institute for Bulgarian Language's answers, kaksepishe.com, and the EU translators' Bulgarian style guide.

## Any Bulgarian text

The checker works on any Bulgarian text, with one rule set. Every rule was measured on seven kinds of text (2026-10-31): marketing e-mails, model-written strings, bg.wikipedia, edited books, bg.wikinews, EU legal acts and the UD treebank. A rule ships only if it holds in all of them.

As a result:
- A capitalised word inside a sentence is a name and is not spelt. That was 51–67% of the spelling flags on general text.
- Glue words found in EU and book text take no comma: по-специално, ама, май, още повече, `10 минути след като`.
- Legal list markers (`iii)`) are not unmatched brackets.

## Morphology (`morphology.py`)

`analyse(word)` returns every reading of a word form, as `(lemma, slot, tag)`. `inflect(lemma, g=, n=, d=, …)` returns that lemma's forms with the asked features. Tags are `POS|feat=val`:
- POS: `N`, `Np`, `Nm` (months), `A`, `V`, `P…`, `Mc`, `Mo`, `R`, `C`, `T`.
- Features: `g` m/f/n; `n` s/p/c (c is the count form); `d` i/h/f/d; `p`; `v`; `voc`; `case`; `clitic`.

The data is built by `tools/morphology/hunspell_morph.py` from the spelling dictionary itself (bgOffice's spell-check package, MPL-1.1) and gramoten's own list of pronouns, numerals and other closed classes. The Hunspell file gives each word's forms; the builder works out the tags from how those forms relate (a verb's `-ш` form is the 2nd person, a noun's `-ът` form is masculine, and so on), so no tag comes from another lexicon. 64,054 lemmas, 1,060,242 readings over 864,104 forms. Files: `data/bg_morph.marisa` (6.9 MB, the readings), `data/bg_morph_lemmas.marisa` (1.6 MB, the lemmas), `data/bg_morph.json` (the tags) and `data/gender_extra.tsv` (173 reviewed gender corrections). They load in a few milliseconds.

Details and rebuild: `tools/morphology/SOURCE.md`.

## Spelling: how it works and what it costs

The dictionary is bgOffice's `bg_BG`, in the copy under GPL/LGPL/MPL that gramoten takes under MPL-1.1 (`tools/bg_BG/SOURCE.md`). Its affix rules are expanded once, at build time, into every word form, and stored in a 2 MB trie: `data/bg_forms.marisa`, holding 866,654 lowercased forms.

- **Checking a word:** look it up in the trie.
- **Suggesting:** three searches, then one ranking.
  - **One edit:** every one-edit change of the word (a letter added, dropped, replaced, or two swapped) that is in the trie. Cost 1.
  - **Sound-alike:** every known word the word becomes by changes that sound the same or nearly so in Bulgarian (`SOUND_ALIKE`): reduced unstressed vowels (`а/ъ`, `о/у`, `е/и`), `я/е`, voiced and voiceless consonants (`б/п`, `в/ф`, `г/к`, `д/т`, `ж/ш`, `з/с`), `я`, `ю` and `щ` spelt by sound (`йа`, `йу`, `шт`), `ия` heard as `еъ`, a lost `т`/`д` (`чесно`), clusters heard as one sound (`дс`/`тс` as `ц`: `ацки` → `адски`; `жт` as `щ`: `вище` → `вижте`; `вств` as `ств`/`св`: `чусвам` → `чувствам`; `хв` as `ф`; `ст` as `з`: `гостба` → `гозба`; `иа` as `я`: `милярд` → `милиард`), and a doubled or undoubled letter. Each change costs 0.5 (`SOUND_COST`), so `хъръктеристикъ` reaches `характеристика` and `фучбол` reaches `футбол` first. It walks the word lists letter by letter, so it takes well under a millisecond.
  - **Two edits:** when fewer than 5 words cost 1 or less. It walks the word lists letter by letter and drops a branch as soon as no known word begins with the letters so far: it finds every word two edits away in 5–15 ms, the same ones every time. Whether a known word begins with some letters is one exact lookup in `data/word_starts.marisa`, every start of every form (`tools/build_word_starts.py`), 3 times as fast as a prefix search in each word list. Cost 2.
  - **Ranking:** cost minus 0.3 × log10 of how often news and Wikipedia use the word (`FREQUENCY_WEIGHT`, `data/bg_frequency.marisa`, Leipzig counts), so a common word can come before a slightly closer rare one. A known misspelling's correction always comes first.

| Measure (Windows dev box) | Result |
|---|---|
| RAM | about 45 MB for the whole process, every list loaded |
| A paragraph | 0.14 ms typical, 3 ms p95 |
| Suggestion quality (3,000 Chitanka misspellings, their listed correction hidden, half not used to set the weights) | right word first 95.6%, in the top 5 99% (letter edits alone: 52% and 68%) |
| Suggestion quality (600 random one-edit typos of common words) | right word first 87%, in the top 5 100% |
| Suggestion quality (600 random two-edit typos of common words) | right word first 65%, in the top 5 88% |

Hunspell engines were measured and rejected:
- **spylls:** up to 94 s for one suggestion.
- **SymSpell:** 167–577 MB of RAM.

**Rebuild the data** (inputs and licence: `tools/`):

```
uv run --no-project --python 3.13 --with spylls==0.1.7 --with marisa-trie==1.4.1 --with psutil python -I tools/build_bg_forms.py
uv run --no-project --python 3.13 --with marisa-trie==1.4.1 python -I tools/morphology/hunspell_morph.py
```

**Modern words, names and counts** (`tools/build_modern_words.py`, sources and licences in `tools/bg_BG/SOURCE.md`):
- **`data/modern_words.marisa`:** 96,866 forms in one list: 46,888 forms the dictionary lacks (`ползватели`, `коронавирус`, `интернета`), from 2M sentences of 2020 news and 2021 Wikipedia (Leipzig, CC BY) and 675M words of 2021 web text (the first 3 GB of MaCoCu-bg) (MaCoCu-bg, CC0; paragraphs in Russian, Serbian or other non-Bulgarian Cyrillic are left out). A word is accepted only when it:
  - appears in two of the three sources; or is long and specialised with no dictionary word close by (`наказателноправни`); or is used 20 times on the web in more than one of its forms (`емболизация`, `пейсмейкър`, `водоструйка`: a typo rarely shows up inflected);
  - is never seen only capitalised;
  - is not a colloquial form, nor `не` glued to a finite verb (`незнаеше`, BERON §62), nor a misspelling Chitanka's table or `corrections.tsv` knows;
  - is not the cut-off start of a word 500 times as frequent (`коронавиру`, `възмо`);
  - is not a likely typo of a much more frequent word one or two edits away. An added ending is not a typo.

  Web-only words also pass two guards: no slip of a spelling used as often or more (`одеалото`, `кетеринг`, `екслузивен`), and not the cut-off start of a word 500 times as frequent (`възмо`, `разполо`). A sample of 300, read word by word, was about 98% right.
- **`data/names.marisa`:** 7,870 words the corpora write capitalised and almost never lowercase, and every word of the names of Bulgaria's settlements from EKATTE, the National Statistical Institute's register (`Кочево`, `Доброславци`; official data, not under copyright). A name at a sentence start is not a typo; in lowercase it is still spelt.
- **Inflected forms, in the same `data/modern_words.marisa`:** 49,978 other forms of the added words (`ламинатът`, `интериорната`), made by `build_inflections.py` with the paradigm of the dictionary word that shares the longest ending and whose forms real text uses most (so MPL-1.1, like the dictionary). A form is kept only when the news, Wikipedia or web text uses it twice, it is no likely typo of a word used 3 times as often, and it is not the cut-off start of a much more used word. Samples of 200 read word by word: about 97.5% right.
- **`data/bg_frequency.marisa`:** counts of 171,988 known forms in the same news and Wikipedia text. They rank suggestions.
- **`data/word_starts.marisa`:** every start of every form in `bg_forms.marisa` and `modern_words.marisa` (1,493,312 starts, 2.9 MB), written by `tools/build_word_starts.py`; the suggestion search asks it whether a known word begins with some letters. Rebuild it whenever those two lists change; a test fails while it is out of date.
- **Abbreviations** (`ул.`, `проф.`, `стр.`) are accepted before a full stop, and **units** (`км`, `кг`) always.
- **`data/telecom_words.txt`:** telecommunications terms with every form (`гигабитът`, `полудуплексните`, `радиорелейни`, `симкартата`, `роуминговите`, `рутерът`). Built by `tools/build_telecom_words.py`: each term declines like a model word of the bgOffice lexicon with the same ending. The terms are the words missing in real telecom Bulgarian: the Electronic Communications Act, the CRC glossary, telecom operators' public pages, 25 bg.wikipedia telecom articles and marketing e-mails (2026-10-31). Typos such as `инфрастурктура` stay flagged. To add a term, put it under its model in the script and rerun it.
- **Chitanka's dictionary** (Речко), from the Hugging Face dataset `vislupus/bulgarian-dictionary-raw-data` under the MIT licence (Chitanka's own code is MIT too, "Copyright (c) 2013 Authors of Chitanka"), built by `build_chitanka.py`:
  - **`data/misspellings.marisa`:** 386,241 misspelling → correction pairs that people searched for. The correction leads the suggestions (`очудване` → `учудване`).
  - **`data/forbidden_words.txt`:** errors the added lists had let in:
    - `не` glued to a finite verb (`незнам`, `неможе`, `незнаейки`, BERON §62). Participles and adjectives are exempt (`неработещ`).
    - Colloquial `-ме` endings (`ходиме`).
    - Chitanka misspellings whose correct form is at least 5 times as common (`фармацефт`).
    - bgOffice always wins: a form it knows is never forbidden.
- **`data/corrections.tsv`:** misspelling → correction pairs written for gramoten (`надежност` → `надеждност`, `верно` → `вярно`): forms the added lists would otherwise accept. They are forbidden and suggested first, before Chitanka's correction for the same word; loanwords (`хаус`, `скраб`) stay allowed. A feminine noun in -ост/-ст without its second т (`радоста`) gets `радостта` first.
- **`data/vocative_words.txt`:** 1,171 forms of address bgOffice lacks (`мамо`, `сине`, `учителю`, `госпожице`, `кралице`, `колего`, `грешнице`). Built by `build_vocatives.py`: the standard vocative of every noun that names a person. A noun names a person when the corpora use its vocative, or by the language itself: Leipzig's sentences count it with `двама`/`трима`/`няколцина` (only people are counted so), or it has a person ending and a feminine pair (`учител`/`учителка`). Nouns whose rule form would be wrong or unsure are left out (`човек` → `човече`, `селянин`, `боец` → `бойче`), and so are -ник/-ница pairs that may be things (`кошница`) unless used. A sample of 200 read word by word had no clear error. Others go in `project_words.txt` (`клиенте`), among them 91 forms of address reviewed one by one (`котко`, `пирате`, `бащице`, `осветителю`) and the `-че` nouns, whose address form is the noun itself (`виетнамче`); things stay out (`банко`, `каско`).
- **`data/eu_words.txt`:** 151 EU legal words (`дерогация`, `внедрители`, `псевдонимизация`, `киберинцидент`). Built by `build_eu_words.py` from 20 Bulgarian EU acts, including the Electronic Communications Code and the roaming regulation. A word must appear in two acts or 5 times in one, with the same typo guard.

**Speed.** A text checks at about 0.19 M characters per second, measured on e-mails and drafts. The time grows with a text's length and no faster: a rule that looks at what comes before a word reads at most 200 characters back (`tokenize.before`). Suggestions are cached per word (the last 20,000 words), so a word is searched once. The two-edit search (5–15 ms a word) runs for the first 20 unknown words of each `check`/`check_many` call (`DEEP_SUGGESTIONS_PER_CALL`), so a text with very many unknown words stays fast: 300 words with 30 two-letter typos check in about 0.21 s. One-edit and sound-alike suggestions are always made (0.5 ms a word). Both limits are counts, not times, so the same text always gets the same suggestions, on any machine.

**Text handling.** Soft hyphens, zero-width marks and combining stress accents inside a word are ignored for the lookup, while offsets keep pointing at the text as written.

**Spelling flags per 1,000 words** (2026-11-04, on text the lists never saw; real typos included): held-out web text 7.18, Leipzig 2022 news 5.90, 34 bg.wikipedia articles 13.92. What remains is mostly rare words, dialect, old spelling and genuine errors (`служащи` for `служещи`).

**`data/project_words.txt`:** the dictionary is from 2017. This file adds modern words by hand, such as смартфон, рутер, имейл and лв; names of people, brands and places are left out. Every line was read by a person, including the about 2,300 added on 2026-11-03 (the most frequent spelling flags of the web text, from `ламинат` to `кератоконус`); misspellings, dialect and old spelling were left out. Real typos found in that list stay out, so they keep being flagged.

## Fonts (`fonts.py`)

`fonts.check(html, house=None)` reads an e-mail's HTML for the fonts a reader will not get. It looks at style attributes, `<style>` blocks and `<font face>` tags, and fetches nothing. It returns one `FontFinding(code, offset, family, stack, message)` per occurrence. `fonts.group(findings)` folds them into one row per code and family, with a count.

| Code | Finding |
|---|---|
| `font_not_loaded` | The first family is no common system font and no `@font-face` in the document loads it. |
| `font_office_leak` | `+mn-ea`, `+mj-lt`: Office theme fonts pasted from Word or Outlook. |
| `font_no_fallback` | The list ends with no `sans-serif`/`serif`. |
| `font_name_variant` | One font written two ways (`BrandSans`, `Brand Sans`). |
| `font_legacy_tag` | A `<font face>` tag. |
| `font_mismatch` | A family outside `house`, the template's own fonts (`fonts.families_in(template_html)`). |

**No house font is assumed.** Pass the template's fonts as `house`. Without it, the body font is the reference: a `p`/`td` rule in a `<style>` block, otherwise `<body style>`. Measured on the corpus, that alone flags every template heading, so a host with a template passes `house`.

**On 471 marketing e-mails** (a private set, 2026-10-30):

| Finding | E-mails |
|---|---|
| A font that never loads: a brand font under three spellings, Calibri, futuraBookRegular | 319 |
| Arial with no fallback (in the shared template itself) | 469 |
| `<font face>` tags | 76 |
| Name variants | 53 |
| Office leaks | 4 |

Whether a web font has Cyrillic glyphs needs the font files and is not checked.

A host that builds e-mails from a template can group findings by origin (the template, or a part the writer fills in) and report a mismatch only in the writer's part.

## Added words

`words.WordStore(path)` keeps the words people add, in one JSON file that is replaced atomically.
- `add(word, by)`: a word is 2–40 Cyrillic letters with at most one hyphen, and is lowercased. A word the dictionary already knows is not stored.
- `remove(word)`
- `words()`: pass this as `extra=`.
- `entries()`: the words with who added them and when.

Who may add is the host's decision.

**An app's own names stay with the app.** A capitalised word inside a sentence is taken as a name, but at a sentence start it is spelt (`Кукушев ще води.`). The names, brands and places one app's texts use do not belong in the shared package: keep them in a file and pass them as `extra=` (`words.load_words(path)` reads a plain list or a `WordStore` file), or on the command line as `--words FILE`.

## Integrating

**1. Install** the package (repository README, "Install") and add `gramoten` to the app's dependencies. Nothing else is needed: no model, no network, no service.

**2. Load the lists once, at start.** The first check loads every word list (about 15 ms; the process then takes about 45 MB). Call it when the app starts, so no user waits for it:

```python
import gramoten

gramoten.check("проверка")
```

**3. Check, and send the findings to the page.** `Issue.to_json()` is the shape a front end reads:

```python
from fastapi import FastAPI  # any web framework works the same way
import gramoten

app = FastAPI()


@app.post("/check")
def check(body: dict) -> dict:
    words = frozenset(w.lower() for w in body.get("extra", []))
    return {"issues": [i.to_json() for i in gramoten.check(body["text"], words)]}
```

`server.py` is the same with the standard library only, at about 90 lines; its `MAX_TEXT` (200,000 characters) is a sensible request limit.

**4. Offsets in JavaScript.** `start` and `end` count Python characters (code points). A JavaScript string counts UTF-16 units, so after an emoji or another character outside the Basic Multilingual Plane the two differ by one. Cyrillic, Latin and the usual punctuation are the same in both. Convert when the text may hold such characters:

```javascript
// Python offset -> JavaScript offset in the same text
function jsOffset(text, pyOffset) {
  return [...text].slice(0, pyOffset).join("").length;
}
```

**5. Apply what the user accepts.** Send back the text and the accepted issues, or apply them in Python: `gramoten.apply_fixes(text, accepted)`. Fixes whose span no longer holds their text are skipped, so a text the user changed meanwhile is safe. Check again afterwards: one fix can reveal another. `gramoten.fix_text(text)` applies every certain fix in one call. Spelling is never fixed automatically; the user picks a suggestion.

**6. Your own words.** Pass the names, brands and terms your texts use as `extra`, a `frozenset` of lowercase words, on every call. Read them from a file with `load_words(path)` (one word per line), or let users add words with `WordStore(path)` and pass `store.words()`; both are in `gramoten.words` (`from gramoten.words import load_words, WordStore`). Different users or teams can pass different sets; nothing is shared between calls.

**7. Threads and processes.** `check` is safe to call from many threads at once (checked: 16 threads give the same findings as one). The word lists are read-only and shared inside a process; each worker process loads its own copy (45 MB each).

**8. Speed.** About 0.2 M characters a second; a 300-word e-mail takes about 12 ms. Suggestions are cached per word, so a text checked again (as the user types) is faster. The two-edit suggestion search runs for the first 20 unknown words of a call (`DEEP_SUGGESTIONS_PER_CALL`), so even 300 words with 30 two-letter typos check in about 0.21 s; the same text always gets the same findings and suggestions.

**9. Placeholders.** Text inside `%%…%%`, AMPscript, URLs and e-mail addresses is never checked or changed ("What is never read"). An editor that puts other code inside words can send it as one `◊`.

**10. Fonts.** For e-mail HTML, `fonts.check(html, house=None)` (`from gramoten import fonts`) lists the fonts a reader will not get ("Fonts").

The tests are in `tests/` at the repository root (`uv run --group dev pytest -q`). Rebuilding the word lists needs the scripts in `tools/` and their downloads; the package itself never does.
