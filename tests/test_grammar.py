"""Grammar and agreement, by the morphology."""

from __future__ import annotations

import unittest

from helpers import fixes

import gramoten
from gramoten import spelling


class Grammar(unittest.TestCase):
    """Rules in lexical.py."""

    def test_sent_errors_with_their_fix(self) -> None:
        cases = {
            "Разполагате с свободни позиции": ("s_sas", "с", "със"),
            "работа с най-бързият процесор": ("article_after_preposition", "най-бързият", "най-бързия"),
            "повече от сумарният капацитет": ("article_after_preposition", "сумарният", "сумарния"),
            "В случай, че до сега не сте": ("written_together", "до сега", "досега"),
            "Ви очаква на 10-12 юли": ("number_range", "10-12", "10–12"),
            "във всеки магазин и и онлайн": ("repeated_word", " и", ""),
            "най много предимства": ("superlative_hyphen", "най много", "най-много"),
            "във България": ("v_vav", "във", "в"),
            "в Франция": ("v_vav", "в", "във"),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertIn(expected, fixes(text, gramoten.KIND_GRAMMAR))

    def test_right_forms_raise_nothing(self) -> None:
        for text in (
            "с SEO и със Spotify",
            "преди срокът да изтече",
            "с лакът",
            "от тогава до сега",
            "в Моят Профил",
            "със или без",
            "защо си си тръгнал",
            "по нов начин",
            "от части на двигателя",
        ):
            with self.subTest(text=text):
                self.assertEqual(fixes(text, gramoten.KIND_GRAMMAR), [])

    def test_a_lowercase_ви_is_not_a_finding(self) -> None:
        """Lowercase „ви“ is correct and is not flagged."""
        both = gramoten.check_many(["Ще Ви се обадим.", "Напомняме ви за отстъпката."])
        self.assertEqual([i.code for i in both[1] if i.kind == gramoten.KIND_GRAMMAR], [])


class Agreement(unittest.TestCase):
    """Rules in grammar.py, using morphology.py (bgOffice)."""

    def test_each_rule_finds_its_error_and_fixes_it(self) -> None:
        cases = {
            "Вашите данните са защитени.": ("double_article", "данните", "данни"),
            "Това е най-добрия избор.": ("article_after_copula", "най-добрия", "най-добрият"),
            "Абонамент за 24 месеци.": ("count_form", "месеци", "месеца"),
            "Дойдоха трима сина.": ("plural_after_dvama", "сина", "синове"),
            "която Вие държи": ("vie_agreement", "държи", "държите"),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertIn(expected, fixes(text, gramoten.KIND_GRAMMAR))

    def test_correct_sentences_that_look_like_errors(self) -> None:
        for text in (
            "Размътили са целия поток.",
            "до доказване на противното",
            "наред с другото",
            "Вие може да изберете.",
            "21 месец",
            "член 68 органите",
            "Имаме двама колеги.",
            "е идния четвъртък",
            "петима студенти",
        ):
            with self.subTest(text=text):
                self.assertEqual(fixes(text, gramoten.KIND_GRAMMAR), [])

    def test_every_form_the_lexicon_knows_is_a_dictionary_word(self) -> None:
        from gramoten import morphology

        [reading] = [r for r in morphology.analyse("месеци") if r.tag["pos"] == "N"]
        self.assertEqual(reading.tag["g"], "m")
        for form in morphology.inflect(reading.lemma):
            self.assertTrue(spelling.in_dictionary(form), form)


class ArticleAfterPreposition(unittest.TestCase):
    def test_a_verb_is_no_article(self) -> None:
        self.assertEqual([i.code for i in gramoten.check("Защо спряха на говорят за това?")], [])

    def test_the_subject_of_a_da_clause_keeps_the_full_article(self) -> None:
        for text in ("расте без обемът да е нараснал.", "вместо директорът да реши."):
            with self.subTest(text=text):
                self.assertEqual([i.code for i in gramoten.check(text)], [])
        self.assertIn("article_after_preposition", [i.code for i in gramoten.check("сочен за извършителят.")])
