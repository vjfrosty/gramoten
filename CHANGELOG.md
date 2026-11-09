# Changelog

All notable changes are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

- A WordPress plugin (`wordpress/`): the checker as a TypeScript port running in the
  browser, with a block editor sidebar and underlines. A test in CI compares its findings
  and fixes with the Python package's on every run. Another CI job drives the plugin in
  real WordPress with Chrome, Firefox, WebKit and Safari.
- Screenshots in the READMEs: the command line, the test page and the WordPress editor.
- `count_form_person`: after a number a noun that names only people takes the plural,
  not the count form: `5 служителя` → `служители`, `120 ученика` → `ученици`. A closed list
  of such nouns; `човек` (`пет човека`), `кандидат` (a vaccine), `оператор`, `член` stay out.
- `vie_agreement` also reads the л-participle: `Вие сте казал`, `Вие не сте ми казала`,
  `Вие сте се регистрирал` → `казали`, `регистрирали`. Adjectives and passive participles
  keep the addressee's sex (`Вие сте поканен`, `доволна`).
- `date_capital`: a month or a weekday after a day or a preposition is in lower case:
  `до 15 Септември` → `септември`, `през Май`, `в Неделя` (ОПР т. 41.1). Not inside „…“,
  not in a title-case heading, and `Август`/`Септември` only after a day or `през`
  (the emperor, the football club).
- Commas with `т.е.`: one before it (`студиа т.е. екипи` → `студиа, т.е. екипи`) and none
  after it (`т.е.,` → `т.е.`, BERON 80.2).
- `comma_indirect_question`: no comma before `дали` after знам, питам, чудя се, видим:
  `Не знам, дали ще дойде` → `Не знам дали ще дойде`; `дали … или …` is left alone.
- `comma_correlative`: `както в София така и в Пловдив` → `както в София, така и в Пловдив`
  (`така и не` is left alone).
- Written together or with a hyphen: `от колкото` → `отколкото` after a comparison,
  `до като` → `докато`, `по ради` → `поради`, `из между` → `измежду`, `току що` → `току-що`,
  `ноу хау` → `ноу-хау`, `министър председател` → `министър-председател`.
  `на истина` and `след обед` were measured and left out: both are often right as written.
- The new rules were read hit by hit on e-mails, web text, bg.wikipedia and Leipzig news
  and Wikipedia sentences: 501 hits in 8.4 million words, 2 of them wrong.
- Written together: `дотук`, `дотам`, `допреди`, `докъде`, `докъдето`,
  `донякъде`, `докогато`, `оттук`, `оттам`, and `доколко`/`доколкото` when
  `колко` does not count a noun (`до колко часа` stays apart); `понастоящем`;
  shades of colour and two compounds: `тъмнозелен`, `светлокафяв`,
  `научноизследователски`, `световноизвестен` (only when the joined word is in the
  dictionary; `научно-технически` keeps its hyphen).
- Ordinals: `7-ма степен` → `7-а`, `8-мата` → `8-ата` (`7-ма души` is a count and stays);
  the article after the ordinal's `и`: `14-ят` → `14-ият`, `21-ят` → `21-вият`
  (it was `21-вят`).
- A year after a full date takes a space: `31.12.2024г.` → `31.12.2024 г.`; a year
  before a dash too (`1991г.-1999г.`); `20 000г.` is no year and is left alone.
- A day's suffix without the hyphen before a month: `1ви Май` → `1 Май`.
- A prefix cut off by a hyphen and a space: `пра- внучката` → `правнучката`.
- `count_form`: `12 063 третокласни пътища` → `пътя` (road), not `пъти` (time).
- `double_article` no longer flags `международния кръстопът`.
- Glued `не` and a verb get the two words as the first suggestion:
  `неможе` → `не може`, `незнам` → `не знам`.
- 245 misspelt forms the project and modern word lists had accepted are flagged,
  with the right word first (`тенесист`, `буклук`, `манияк`, `фърлям`, `токущо`,
  `тинейджър` → `тийнейджър`); their `project_words.txt` lines are commented out.
- Real words added with their forms: `сервисите`, `недоразбирам`, `машинерия`,
  `бан`, `ноу-хау`, `земеподобен`, `кранов`, `колците`, `деребействам`, `кардия`;
  hyphenated compounds whose first part is a combining form (`австро-унгарски`,
  `гръко-римски`).
- The inflected forms are also made from the telecom and EU word lists.
- The articled plural of an accepted plural is accepted even when text never used it:
  `антивирусите`, `брандингите`, `видеомонтажите`, `мегасъбитията` (3,052 forms).
  About 40 misspelt forms in the modern word list that this exposed are now
  corrected (`абцеси` -> `абсцеси`, `черезвичайни` -> `чрезвичайни`, `искусство` -> `изкуство`).
- Sound-alike suggestions also know clusters heard as one sound: `ацки` → `адски`,
  `площа` → `площта`, `вище` → `вижте`, `чусвам` → `чувствам`, `милярд` → `милиард`
  (right word first on words written by sound: 95.1% → 95.6%).
- `участвувам` and all its forms are flagged, `участвам` first (the form was dropped
  from the norm); `наименувам` stays correct.
- Dialect forms and slips the modern word list had accepted are flagged: `таквоз` → `такъв`,
  `тогоз` → `този`, `оногоз` → `онзи`, `гешеф` → `гешефт`, `байряк` → `байрак`,
  `синур` → `синор`, `медиа` → `медия` (`медиа-групата` is still accepted).
- gramoten's own corrections now come before Chitanka's: `гешеф` → `гешефт` (not `гешев`),
  `военоначалник` → `военачалник`, `фъргам` → `хвърлям`.
- 91 forms of address (`котко`, `пирате`, `бащице`, `осветителю`) and the `-че`
  diminutives (`виетнамче`) are accepted; things stay out (`банко`, `каско`).
- `tools/build_inflections.py` takes about 80 seconds instead of 22 minutes, with the
  same output: the models for each ending are worked out once.
- Suggestions are 2.5 times as fast, with the same results: the search asks one
  trie of every word start (`data/word_starts.marisa`, built by
  `tools/build_word_starts.py`) instead of a prefix search in each word list. A
  300-word text with 30 two-letter typos checks in about 0.21 s instead of 0.45 s.
  The wheel is about 1.4 MB larger and a process about 5 MB.

## [0.1.0] - 2026-11-03

First release.

- Spelling against the bgOffice dictionary (866,654 forms), with modern words,
  their inflected forms, forms of address, telecom and EU legal terms, names and
  settlement names.
- Suggestions by letter edits and by sound: changes that sound alike in
  Bulgarian (reduced vowels, voiced and voiceless consonants, `я`/`йа`, a lost
  `т`) count as half an edit, then word frequency ranks them.
  Words written by sound get the right word first 95% of the time.
- Format, punctuation, wording and grammar rules, each with a certain fix where
  one exists (`apply_fixes`, `fix_text`).
- Mixed Latin and Cyrillic letters inside a word.
- Font checks for e-mail HTML (`gramoten.fonts`).
- Command line (`gramoten FILE`, `--words FILE`) and a local test page
  (`gramoten serve`).
