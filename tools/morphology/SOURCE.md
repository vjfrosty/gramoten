# Bulgarian morphology: source and rebuild

`src/gramoten/data/bg_morph.marisa`, `bg_morph_lemmas.marisa` and `bg_morph.json` are built by `hunspell_morph.py` from:

- **`../bg_BG/bg_BG.dic` and `bg_BG.aff`**: bgOffice's spell-check dictionary, in the copy
  under GPL/LGPL/MPL, which gramoten takes under **MPL-1.1** (`../bg_BG/SOURCE.md`).
- **`closed_words.tsv`**: pronouns, numerals, month names, prepositions, conjunctions and
  particles, plus a few nouns and adjectives the endings cannot place (plural-only `данни`,
  irregular plurals `хора`, `деца`, `очи`, `имена`, `дни`; `десен`: `дясна`). Written for
  gramoten from Bulgarian grammar, with the code's licence.

No tag is copied from another lexicon. The Hunspell file says only which endings each word
takes; `hunspell_morph.py` works out what each form is from how a word's forms relate,
the same way for every affix class:

- **verbs:** the entry is the 1st person singular present. `-ш` marks the 2nd person, which
  without `ш` is the 3rd; a stem with `-ше` and `-х` is the imperfect (with я/е: `четеше`,
  `четях`); a stem with `-х` and `-хме` whose 3rd person is a form is the aorist (`четох`:
  `чете`, `пекох`: `пече`); `-л` with `-ла`, `-лия`... is a participle, imperfect when its
  stem is the imperfect's; `-щ` the present participle, `-н`/`-т` with `-на`/`-та` the
  passive one, `-йки` the gerund, `-ете`/`-йте` the imperative.
- **nouns:** the gender comes from the ending and the article (`-ът`/`-ят` masculine, `-та`
  feminine, `-то` neuter; `MASCULINE_IN_VOWEL` for `баща`, `дядо`...); the plural is the form
  that takes `-те`/`-та`; a masculine noun's short article is also its count form, except
  for persons with a vocative in `-ю`; what is left over is a vocative.
- **adjectives:** a word with `-ият`, `-ата`, `-ото`/`-ето` and `-ите` forms; ordinals
  (`ORDINALS`) are tagged `Mo`.
- **entries with several flags** that are two words (`гол`: naked, and a goal) become two lemmas.
- **words the dictionary lists form by form**, without endings (irregular verbs such as `държа`,
  nouns such as `песен`): consecutive entries sharing their first word's stem are one word.
  The rules above run on the group first; forms they leave are tagged by analogy, from the
  endings of the words already labelled (an ending of 2-6 letters that at least 20 labelled
  words share and that at least 85% of them agree on).

Result: 64,054 lemmas, 1,060,242 readings over 864,104 forms; 9.6 MB.

## How it was checked

- **Grammar rules:** errors planted in 34 random bg.wikipedia articles (a double article, a
  plural after a number, a count form after трима, a wrong verb after Вие, a short article
  after е). One run caught: double article 176 of 218, count form 9 of 20, Вие agreement
  194 of 300, article after a copula 113 of 119. On the clean articles nothing is raised.
- **Tests:** all pass (`tests/`).

## Rebuild

```
uv run --no-project --python 3.13 --with marisa-trie==1.4.1 python -I tools/morphology/hunspell_morph.py
```

About 10 s. It prints how many words and forms it could not label.

## `gender_extra.tsv`

173 nouns with an extra gender (`base<TAB>genders`), read by `grammar.py`: found from gender
contradictions in edited text (bg.wikipedia, bg.wikinews, EU acts), each read by a person.
gramoten's own list, under the code's licence.
