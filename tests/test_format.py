"""Format: mixed scripts, typography, prices, orthography."""

from __future__ import annotations

import time
import unittest

from helpers import fixes

import gramoten
from gramoten import mixed_script, spelling, tokenize


class MixedScript(unittest.TestCase):
    def test_sent_words_are_found_and_fixed(self) -> None:
        cases = {
            "пoлучавате": "получавате",  # Latin o
            "Виe": "Вие",  # Latin e
            "aко": "ако",  # Latin a
            "Kомбинирайте": "Комбинирайте",
            "ВMW": "BMW",  # Cyrillic В in a Latin brand
        }
        for word, fixed in cases.items():
            with self.subTest(word=word):
                [issue] = gramoten.check_spelling(f"Текст {word} тук")
                self.assertEqual(issue.code, gramoten.MIXED_SCRIPT)
                self.assertEqual(issue.fix, fixed)

    def test_an_even_split_or_a_letter_without_lookalike_gets_no_fix(self) -> None:
        self.assertIsNone(mixed_script.fix("МАЗMAX"))  # 3 and 3
        self.assertIsNone(mixed_script.fix("сmарт"))  # Latin m has no lookalike

    def test_hyphen_parts_keep_their_own_script(self) -> None:
        self.assertFalse(tokenize.Word("SIM-карта", 0, 9).mixed_script)
        self.assertEqual(mixed_script.fix("SIM-кaрта"), "SIM-карта")


class Format(unittest.TestCase):
    def test_each_rule_offers_its_one_correction(self) -> None:
        cases = {
            "Вижте  тук": ("double_space", "  ", " "),
            "оферта за .": ("space_before_punctuation", " .", "."),
            "Музика - избирайте": ("dash", " - ", " – "),
            'съобщение "няма сигнал"': ("quotes", '"няма сигнал"', "„няма сигнал“"),
            "Звездите са подредени...": ("ellipsis", "...", "…"),
            "само 21.99 лв.": ("decimal_separator", "21.99", "21,99"),
            "дума,дума": ("space_after_punctuation", ",", ", "),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertIn(expected, fixes(text, gramoten.KIND_FORMAT))

    def test_a_number_and_its_unit_are_kept_together_quietly(self) -> None:
        [issue] = [i for i in gramoten.check("само 350 лв.") if i.code == "nbsp_number_unit"]
        self.assertTrue(issue.quiet)
        self.assertEqual(issue.fix, "\u00a0")

    def test_links_and_tokens_are_not_format(self) -> None:
        self.assertEqual(fixes("Посетете www.example.bg/a...b и %%=v(@x)  =%%", gramoten.KIND_FORMAT), [])


class Euro(unittest.TestCase):
    """Prices are in euro; a price in leva is flagged, never converted."""

    def test_a_price_in_leva_is_found_and_no_amount_is_offered(self) -> None:
        for text, price in (
            ("Цена 9,99 лв./мес.", "9,99 лв."),
            ("само 1 059,38 лв. без ДДС", "1 059,38 лв."),
            ("до 350 лева", "350 лева"),
            ("10 BGN", "10 BGN"),
        ):
            with self.subTest(text=text):
                [issue] = [i for i in gramoten.check(text) if i.code == "currency_bgn"]
                self.assertEqual((issue.text, issue.fix, issue.suggestions), (price, None, ()))

    def test_the_euro_sign_goes_after_the_amount(self) -> None:
        self.assertIn(("euro_symbol_position", "€9.99", "9,99 €"), fixes("само €9.99 на месец", gramoten.KIND_FORMAT))
        self.assertIn(("euro_symbol_position", "EUR 10", "10 €"), fixes("EUR 10 отстъпка", gramoten.KIND_FORMAT))
        self.assertEqual([i.code for i in gramoten.check("9,99 € на месец")], [])


class Orthography(unittest.TestCase):
    """orthography.py: IBL rules, BERON and the DGT style guide."""

    def test_each_rule_and_its_fix(self) -> None:
        cases = {
            "Дадох й книгата.": ("pronoun_i", "й", "ѝ"),
            "5-ти етаж": ("ordinal_suffix", "5-ти", "5-и"),
            "47-ми председател": ("ordinal_suffix", "47-ми", "47-и"),
            "12-та среща": ("ordinal_suffix", "12-та", "12-а"),
            "в 53-ата минута": ("ordinal_suffix", "53-ата", "53-тата"),
            "1-и ден": ("ordinal_suffix", "1-и", "1-ви"),
            "7-ма степен": ("ordinal_suffix", "7-ма", "7-а"),
            "8-мата година": ("ordinal_suffix", "8-мата", "8-ата"),
            "14-ят ден": ("ordinal_suffix", "14-ят", "14-ият"),
            "21-ят век": ("ordinal_suffix", "21-ят", "21-вият"),
            "2-ят етап": ("ordinal_suffix", "2-ят", "2-рият"),
            "на 9-ти март": ("ordinal_date", "9-ти", "9"),
            "по повод 1ви Май": ("ordinal_date", "1ви", "1"),
            "XXI-ви век": ("ordinal_roman", "XXI-ви", "XXI"),
            "19 годишен младеж": ("number_adjective", "19 годишен", "19-годишен"),
            "пет-годишен план": ("number_adjective", "пет-годишен", "петгодишен"),
            "10%-на отстъпка": ("percent_adjective", "10%-на", "10-процентна"),
            "Уважаеми г-н. Иванов": ("title_period", "г-н.", "г-н"),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertIn(expected, [(i.code, i.text, i.fix) for i in gramoten.check(text)])

    def test_correct_ordinals_and_counts_are_not_flagged(self) -> None:
        for text in (
            "1-ви, 2-ри, 3-ти, 4-ти, 5-и, 12-и, 21-ви",
            "през 80-те години",
            "27-те страни",
            "100-на активисти",
            "10-ки хиляди",
            "в 14:00 местно време",
            "95 вековни дървета",
            "параграф 6 годишни доклади",
            "Й. Петров",
            "5-годишен",
            "5-ма души",
            "1ви етаж",
            "7-ма души",
            "14-ият ден",
            "21-вият век",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    [
                        i.code
                        for i in gramoten.check(text)
                        if i.code
                        in ("pronoun_i", "ordinal_suffix", "ordinal_date", "ordinal_roman", "number_adjective")
                    ],
                    [],
                )


class AssessmentFixes(unittest.TestCase):
    """Cases where a rule fired wrongly or missed an error."""

    def test_a_doubled_preposition_is_a_repeated_word_not_v_vav(self) -> None:
        self.assertEqual([i.code for i in gramoten.check("влиза в в парламента")], ["repeated_word"])

    def test_a_list_letter_is_not_a_repeated_word(self) -> None:
        self.assertEqual(gramoten.check("букви з) и и), както"), [])

    def test_the_dictionary_decides_a_tied_mixed_script_word(self) -> None:
        self.assertIn(("mixed_script", "oт", "от"), fixes("се oткажат oт това", gramoten.KIND_FORMAT))
        self.assertIn(("mixed_script", "пo-къснo", "по-късно"), fixes("минути пo-къснo тук", gramoten.KIND_FORMAT))

    def test_two_commas_for_an_opening_quote(self) -> None:
        self.assertEqual(fixes("техникум ,,Хенри Форд”", gramoten.KIND_PUNCTUATION), [("comma_comma_quote", ",,", "„")])

    def test_long_specialised_words_are_known(self) -> None:
        for word in ("наказателноправни", "термообработка", "предклинични"):
            with self.subTest(word=word):
                self.assertTrue(spelling.is_correct(word))
        for word in ("коронавиру", "вирусулогът", "мюслимска"):
            with self.subTest(word=word):
                self.assertFalse(spelling.is_correct(word))

    def test_a_long_text_of_unknown_words_stays_fast(self) -> None:
        text = " ".join(f"Зъклофрит{i}ане".replace(str(i), "") + f" щрумбалезия{chr(1072 + i % 30)}" for i in range(60))
        started = time.perf_counter()
        gramoten.check_many([text])
        self.assertLess(time.perf_counter() - started, 1.5)


class FalseAlarmsOnNews(unittest.TestCase):
    """Correct text the orthography rules must leave alone."""

    def test_a_cut_off_word_after_a_number_is_no_ordinal(self) -> None:
        self.assertEqual([i.code for i in gramoten.check("отбелязаха 30-годи.") if i.code != "spelling"], [])

    def test_a_number_that_counts_the_noun_takes_no_hyphen(self) -> None:
        for text in ("над 10 процентни пункта", "в 3 часови пояса"):
            with self.subTest(text=text):
                self.assertNotIn("number_adjective", [i.code for i in gramoten.check(text)])
        self.assertIn("number_adjective", [i.code for i in gramoten.check("каза 22 годишното крило")])
