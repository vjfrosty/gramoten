"""Punctuation: commas before conjunctions and relatives."""

from __future__ import annotations

import unittest

from helpers import fixes

import gramoten


class Punctuation(unittest.TestCase):
    def test_missing_commas_are_found_with_a_fix(self) -> None:
        cases = {
            "Какво да направите ако не помните паролата": " ако",
            "Данните струват повече отколкото предполагате": " отколкото",
            "Бъдете защитени докато сърфирате онлайн": " докато",
            "Знаем че обичате филми": " че",
            "Гледайте каналите след като ги активирате": " след като",
            "Имаме оферта но е само до петък": " но",
            "Това е телефонът който търсите": " който",
        }
        for text, gap in cases.items():
            with self.subTest(text=text):
                found = fixes(text, gramoten.KIND_PUNCTUATION)
                self.assertEqual(found, [(found[0][0], gap, "," + gap)])

    def test_a_compound_conjunction_is_not_split(self) -> None:
        self.assertEqual(
            fixes("В случай, че имате нужда", gramoten.KIND_PUNCTUATION),
            [("comma_inside_compound", "В случай, че", "В случай че")],
        )

    def test_the_greeting_takes_a_comma_before_the_name(self) -> None:
        self.assertEqual(
            fixes("Здравейте Иване", gramoten.KIND_PUNCTUATION),
            [("comma_vocative", "Здравейте Иване", "Здравейте, Иване")],
        )

    def test_correct_sentences_raise_nothing(self) -> None:
        for text in (
            "Дори когато сте в чужбина, имате интернет.",
            "Вземи която искаш.",
            "Знаем, че обичате филми, защото и ние ги обичаме.",
            "Освен ако не желаете друго, планът остава.",
            "Може би когато дойдете, ще разберете.",
            "Здравейте, %%FirstName%%!",
            "Нито едно, нито друго.",
        ):
            with self.subTest(text=text):
                self.assertEqual(fixes(text, gramoten.KIND_PUNCTUATION), [])

    def test_te_dali_and_tak_i(self) -> None:
        cases = {
            "Съветът не е компетентен, т.е., няма право.": ("comma_after_te", "т.е.,", "т.е."),
            "Т.е., не.": ("comma_after_te", "Т.е.,", "Т.е."),
            "Има няколко студиа т.е. доста екипи.": ("comma_before_conjunction", " т.е.", ", т.е."),
            "Не знам, дали ще дойде.": ("comma_indirect_question", ", ", " "),
            "Чудя се, дали е вярно.": ("comma_indirect_question", ", ", " "),
            "Да видим, дали ще стане.": ("comma_indirect_question", ", ", " "),
            "Работим както в София така и в Пловдив.": ("comma_correlative", " така и", ", така и"),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertIn(expected, fixes(text, gramoten.KIND_PUNCTUATION))

    def test_te_dali_and_tak_i_near_misses(self) -> None:
        for text in (
            "Това е, т.е. важно е.",
            "Не знам дали ще дойде.",
            "Не знам, как да го кажа.",
            "Зависи, дали ще вали или не.",
            "Попитах го, дали ще дойде.",
            "Ще дойда, дали искаш или не.",
            "Работим както в София, така и в Пловдив.",
            "Както казах така и не дойде.",
            "Това е и т.е. не е.",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    [
                        c
                        for c, _, _ in fixes(text, gramoten.KIND_PUNCTUATION)
                        if c in ("comma_after_te", "comma_indirect_question", "comma_correlative")
                        or (c == "comma_before_conjunction" and "т.е" in text)
                    ],
                    [],
                )

    def test_unclosed_marks(self) -> None:
        codes_found = [i.code for i in gramoten.check("концерт „Старият Криско (и още")]
        self.assertIn("unbalanced_quote", codes_found)
        self.assertIn("unbalanced_bracket", codes_found)
