# Changelog

All notable changes are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-03

First release.

- Spelling against the bgOffice dictionary (866,654 forms), with modern words,
  their inflected forms, forms of address, telecom and EU legal terms, names and
  settlement names; suggestions ranked by word frequency.
- Format, punctuation, wording and grammar rules, each with a certain fix where
  one exists (`apply_fixes`, `fix_text`).
- Mixed Latin and Cyrillic letters inside a word.
- Font checks for e-mail HTML (`gramoten.fonts`).
- Command line (`gramoten FILE`, `--words FILE`) and a local test page
  (`gramoten serve`).
