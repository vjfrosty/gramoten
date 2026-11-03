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

    def test_unclosed_marks(self) -> None:
        codes_found = [i.code for i in gramoten.check("концерт „Старият Криско (и още")]
        self.assertIn("unbalanced_quote", codes_found)
        self.assertIn("unbalanced_bracket", codes_found)
