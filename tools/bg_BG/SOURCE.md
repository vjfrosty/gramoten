# Sources of the word lists

## bg_BG Hunspell dictionary

`bg_BG.dic` and `bg_BG.aff` are the Bulgarian spelling dictionary of the bgOffice
project (https://sourceforge.net/projects/bgoffice/), Copyright (C) 2001-2010
Radostin Radnev, in the copy Mozilla ships for Firefox and Thunderbird
("fx+tb+sm-bg", version 4.2 or later):

- https://github.com/elastic/hunspell/tree/master/dicts/bg_BG, commit
  `eb5f2975c1466c8b336e592a3feed43473da9452`, files `bg.dic`, `bg.aff`
- SHA-256: `bg.dic` `c1d403ecf6588c3e23f9b57db2f905fda035e17c115d05736e1ce02ea17dacee`,
  `bg.aff` `fd55a1949266f74a5a246bb3f7d3bef65cd34c9751c57811132a8c8ea668e2b7`
- Changed here: converted from Windows-1251 with CRLF to UTF-8 with LF, and the
  `.aff`'s first line `SET windows-1251` made `SET UTF-8`. Nothing else.

**Licence:** GPL-2.0-or-later, LGPL-2.1-or-later or MPL-1.1, at the user's choice
(`Copyright`, `ChangeLog`). gramoten takes it under **MPL-1.1** (`MPL-1.1.txt`).

The files are input to `../build_bg_forms.py` only; nothing at runtime reads them.

## Modern words, names and word counts

`build_modern_words.py` writes `modern_words.marisa`, `names.marisa` and
`bg_frequency.marisa` from:

- **Leipzig Corpora Collection**, `bul_news_2020_1M` and `bul_wikipedia_2021_1M`,
  CC BY (https://wortschatz.uni-leipzig.de/en/usage). Only word counts and names
  derived from them are kept, never a sentence.
- **MaCoCu-bg 2.0** web text, CC0 (http://hdl.handle.net/11356/1800): the zip's first
  3 GB, counted by `build_web_counts.py`.
- **EKATTE**, the National Statistical Institute's register of settlements
  (https://www.nsi.bg/nrnm/ekatte/index, Excel archive): settlement names for
  `names.marisa`. Official data, not subject to copyright (ЗАПСП, чл. 4).

The downloads are about 4 GB and stay outside the repository.

## Other built lists

- `build_inflections.py`: other forms of the added words, made with the paradigms of
  the bgOffice dictionary (MPL-1.1), added to `modern_words.marisa`, checked against
  the Leipzig and MaCoCu-bg counts.
- `build_word_starts.py`: every start of every form in `bg_forms.marisa` and
  `modern_words.marisa`, for the suggestion search (MPL-1.1, like the dictionary).
  Run it after either list is rebuilt.
- `build_vocatives.py`: forms of address, from the dictionary and the same counts.
- `build_eu_words.py`: EU legal words from 20 Bulgarian acts on EUR-Lex (© European
  Union, reuse under Commission Decision 2011/833/EU). The acts are not kept here.
- `build_chitanka.py`: the misspelling table (`incorrect_forms.csv`) of
  https://huggingface.co/datasets/vislupus/bulgarian-dictionary-raw-data, a copy of
  rechnik.chitanka.info, MIT ("Copyright (c) 2013 Authors of Chitanka"), with
  `words.csv` for the correct forms. Chitanka's word forms are not used.
