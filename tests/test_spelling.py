"""Spelling: the dictionary, the added word lists, corrections and suggestions."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from helpers import SENT_TYPOS, codes, fixes

import gramoten
from gramoten import spelling
from gramoten.words import WordError, WordStore


class Spelling(unittest.TestCase):
    def test_sent_typos_are_flagged_with_the_right_suggestion(self) -> None:
        for typo, right in SENT_TYPOS.items():
            with self.subTest(typo=typo):
                self.assertFalse(spelling.is_correct(typo))
                self.assertIn(right, spelling.suggest(typo))

    def test_correct_text_has_no_finding(self) -> None:
        text = (
            "Здравейте, получавате по-добра оферта за най-новите смартфони "
            "и рутер с 20% отстъпка до 31.12. Цена 9,99 лв./мес. с ДДС."
        )
        self.assertEqual(codes(text), [])

    def test_capitalisation_is_kept_in_suggestions(self) -> None:
        self.assertEqual(spelling.suggest("Консулатант")[0], "Консултант")
        self.assertEqual(spelling.suggest("КОНСУЛАТАНТ")[0], "КОНСУЛТАНТ")

    def test_acronyms_are_not_spelt(self) -> None:
        for word in ("ДДС", "ЕАД", "УЕФА", "ТВ"):
            self.assertTrue(spelling.is_correct(word))

    def test_every_project_word_is_lowercase_and_unknown_to_the_dictionary(self) -> None:
        for word in spelling.project_words():
            self.assertEqual(word, word.lower())
        self.assertFalse(set(SENT_TYPOS) & spelling.project_words())

    def test_a_suggestion_is_fast(self) -> None:
        started = time.perf_counter()
        for typo in SENT_TYPOS:
            spelling.suggest(typo)
        self.assertLess((time.perf_counter() - started) / len(SENT_TYPOS), 0.2)

    def test_offsets_point_at_the_word(self) -> None:
        text = "Вашият консулатант ще се свърже."
        [issue] = gramoten.check_spelling(text)
        self.assertEqual(text[issue.start : issue.end], "консулатант")
        self.assertEqual(issue.kind, "spelling")
        self.assertIsNone(issue.fix)


class Protected(unittest.TestCase):
    def test_tokens_links_and_ampscript_are_never_read(self) -> None:
        text = (
            "%%FirstName%%, вижте https://www.example.bg/смартфонии и пишете на "
            "инфо@example.bg %%=v(@цнеа)=%% %%[ set @хххх = 1 ]%%"
        )
        self.assertEqual(codes(text), [])

    def test_latin_words_and_codes_are_not_spelt(self) -> None:
        self.assertEqual(codes("Netflix, iPhone 16 Pro, 5G и SIM-карта"), [])


class AddedWords(unittest.TestCase):
    def test_added_words_are_checked_and_kept_across_stores(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = WordStore(Path(folder) / "words.json")
            self.assertTrue(store.add("Ивелинка", by="editor"))
            self.assertFalse(store.add("ивелинка", by="admin"))  # already there
            self.assertFalse(store.add("получавате", by="admin"))  # the dictionary knows it
            self.assertEqual(WordStore(Path(folder) / "words.json").words(), frozenset({"ивелинка"}))
            self.assertEqual(codes("Ивелинка ще се обади"), [("spelling", "Ивелинка")])
            self.assertEqual([i.code for i in gramoten.check("Ивелинка ще се обади", store.words())], [])
            self.assertTrue(store.remove("Ивелинка"))
            self.assertFalse(store.remove("ивелинка"))

    def test_only_a_word_can_be_added(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = WordStore(Path(folder) / "words.json")
            for bad in ("a", "iPhone", "две думи", "<b>", "а" * 41, "е--тикет"):
                with self.subTest(bad=bad), self.assertRaises(WordError):
                    store.add(bad, by="x")


class GeneralText(unittest.TestCase):
    """The checker works on any Bulgarian text."""

    def test_a_capital_inside_a_sentence_is_a_name(self) -> None:
        self.assertEqual(codes("Обадете се на Ивелинка"), [])
        self.assertEqual(codes("Ивелинка ще се обади"), [("spelling", "Ивелинка")])
        self.assertEqual(codes("Вашият консулатант"), [("spelling", "консулатант")])

    def test_glue_words_found_in_eu_and_book_text_take_no_comma(self) -> None:
        for text in (
            "по-специално когато дойде",
            "ама че работа",
            "май че е така",
            "още повече че знаем",
            "10 минути след като дойде",
        ):
            with self.subTest(text=text):
                self.assertEqual(fixes(text, gramoten.KIND_PUNCTUATION), [])

    def test_legal_list_markers_are_not_brackets(self) -> None:
        self.assertNotIn("unbalanced_bracket", [i.code for i in gramoten.check("буква iii) и точка iv) от член 5")])


class ModernWordsAndRobustText(unittest.TestCase):
    """Modern words the 2017 dictionary lacks."""

    def test_modern_words_from_news_and_wikipedia_are_known(self) -> None:
        for word in ("ползватели", "правоприлагане", "коронавирус", "брифинг", "еврозоната", "интернета"):
            with self.subTest(word=word):
                self.assertTrue(spelling.is_correct(word))

    def test_typos_and_colloquial_forms_stay_out(self) -> None:
        for word in ("матерял", "кво", "служащи", "използавне", "кандидатсвам"):
            with self.subTest(word=word):
                self.assertFalse(spelling.is_correct(word))

    def test_abbreviations_units_and_names(self) -> None:
        self.assertEqual(codes("На ул. Раковски, на 5 км от центъра, проф. Иванов."), [])
        self.assertEqual(codes("Обама пристигна вчера."), [])
        self.assertEqual(codes("бул без точка"), [("spelling", "бул")])

    def test_invisible_characters_inside_a_word(self) -> None:
        for text in ("полу­чавате оферта", "получа́вате", "за​щитени данни"):
            with self.subTest(text=text):
                self.assertEqual(codes(text), [])
        [issue] = gramoten.check_spelling("консула­тант")
        self.assertEqual((issue.start, issue.end), (0, 12))
        self.assertIn("консултант", issue.suggestions)

    def test_words_written_as_they_sound_get_the_right_word_first(self) -> None:
        # None of these is in a misspelling list: the sound-alike search finds them.
        cases = {
            "фучбол": "футбол",
            "градинъта": "градината",
            "здрафейти": "здравейте",
            "телефуна": "телефона",
            "юнушескъ": "юношеска",
            "млекуту": "млякото",
        }
        for wrong, right in cases.items():
            with self.subTest(wrong=wrong):
                self.assertIsNone(spelling.known_correction(wrong))
                self.assertEqual(spelling.suggest(wrong)[0], right)

    def test_suggestions_rank_by_general_bulgarian(self) -> None:
        self.assertEqual(spelling.suggest("тлефон")[0], "телефон")


class TelecomTerms(unittest.TestCase):
    """Telecommunications terms, with every form."""

    def test_every_form_of_a_telecom_term_is_known(self) -> None:
        for word in (
            "гигабит",
            "гигабитът",
            "гигабитите",
            "гигабайта",
            "симкартата",
            "полудуплексните",
            "радиорелейни",
            "роуминговите",
            "безлимитна",
            "двуфакторна",
            "топологии",
            "оплетки",
            "транспондерите",
            "хотспота",
            "комутируема",
            "междуоперативността",
            "далекосъобщителни",
        ):
            with self.subTest(word=word):
                self.assertTrue(spelling.is_correct(word))

    def test_typos_of_telecom_words_are_still_typos(self) -> None:
        for word in ("гигабтит", "симкатра", "роуминга", "рутерът", "инфрастурктура"):
            with self.subTest(word=word):
                expected = word in ("роуминга", "рутерът")  # the last two are right
                self.assertEqual(spelling.is_correct(word), expected)

    def test_a_telecom_sentence_reads_clean(self) -> None:
        text = (
            "Двуфакторната защита, безлимитните гигабайти и роуминговите услуги на оператора "
            "работят и през хотспота, с полудуплексни радиорелейни връзки и симкарта."
        )
        self.assertEqual(codes(text), [])


class AddressAndLaw(unittest.TestCase):
    """Forms of address, and EU legal words, from corpora with typo guards."""

    def test_forms_of_address(self) -> None:
        for word in ("мамо", "сине", "попе", "клиенте", "учителю", "госпожице", "президенте"):
            with self.subTest(word=word):
                self.assertTrue(spelling.is_correct(word))
        for word in ("минуто", "годино", "карто", "затворе"):
            with self.subTest(word=word):
                self.assertFalse(spelling.is_correct(word))

    def test_forms_of_address_of_nouns_that_name_people(self) -> None:
        """A noun counted with `двама` or with a feminine pair (`учител`/`учителка`) names a person."""
        for word in ("кралице", "учителко", "грешнице", "пилоте", "колего", "слуго", "принцесо", "сътруднице"):
            with self.subTest(word=word):
                self.assertTrue(spelling.is_correct(word))
        # The rule's form would be wrong (`човече`, `бойче`) or the noun a thing (`брояч`, `конница`).
        for word in ("ученике", "човеке", "боче", "брояче", "коннице", "столе", "тенисе"):
            with self.subTest(word=word):
                self.assertFalse(spelling.is_correct(word))

    def test_eu_legal_words(self) -> None:
        for word in ("дерогацията", "внедрители", "псевдонимизация", "киберинцидент", "преддоговорна"):
            with self.subTest(word=word):
                self.assertTrue(spelling.is_correct(word))


class Chitanka(unittest.TestCase):
    """Chitanka's searched misspellings, and the web tier of the modern words (MaCoCu-bg)."""

    def test_the_web_tier_knows_words_the_dictionary_lacks(self) -> None:
        for word in ("емболизация", "бомбоубежища", "пейсмейкър", "водоструйка", "ползватели"):
            with self.subTest(word=word):
                self.assertTrue(spelling.is_correct(word))

    def test_the_web_tier_keeps_out_slips_and_cut_off_words(self) -> None:
        """A slip of a spelling used as often is no word, even when web text repeats it;
        nor is the start of a word cut off at a line break."""
        for word in (
            "тийнеджъри",
            "екслузивен",
            "одеалото",
            "съдомиална",
            "кетеринг",
            "възмо",
            "сокоизтисквачка",
            "парадонтоза",
        ):
            with self.subTest(word=word):
                self.assertFalse(spelling.is_correct(word))
        # The same shapes between two real words: `лавинните` (from `лавинен`) beside
        # `лавините`, `джонка` beside `джанка`, `придадем` beside `предадем`.
        for word in ("лавинните", "джонка", "придадем", "колумбийката", "шумопотискане", "пинсети"):
            with self.subTest(word=word):
                self.assertTrue(spelling.is_correct(word))

    def test_known_errors_are_flagged(self) -> None:
        for word in ("незнам", "неможе", "незнаейки", "ходиме", "платиме", "фармацефт", "туберколоза", "напредвид"):
            with self.subTest(word=word):
                self.assertFalse(spelling.is_correct(word))

    def test_what_looks_like_an_error_and_is_not(self) -> None:
        for word in ("неработещ", "неконтролиран", "хаус", "кампус"):
            with self.subTest(word=word):
                self.assertTrue(spelling.is_correct(word))
        # Rare real words: flagged or not, never as a known error.
        for word in ("нелюбим", "неизтребим", "недоразбирам", "годенице"):
            with self.subTest(word=word):
                self.assertNotIn(word, spelling.forbidden_words())

    def test_the_correction_people_searched_for_comes_first(self) -> None:
        self.assertEqual(spelling.suggest("очудване")[0], "учудване")
        self.assertEqual(spelling.suggest("корегирам")[0], "коригирам")
        self.assertEqual(spelling.suggest("Безмислено")[0], "Безсмислено")


class Corrections(unittest.TestCase):
    """Known corrections: Chitanka's searched misspellings and gramoten's own list."""

    def test_the_own_list_flags_and_corrects(self) -> None:
        for wrong, right in (
            ("надежност", "надеждност"),
            ("мошенник", "мошеник"),
            ("верно", "вярно"),
            ("асвалт", "асфалт"),
        ):
            with self.subTest(wrong=wrong):
                self.assertFalse(spelling.is_correct(wrong))
                self.assertEqual(spelling.suggest(wrong)[0], right)
        for loanword in ("хаус", "скраб", "друид"):
            with self.subTest(loanword=loanword):
                self.assertTrue(spelling.is_correct(loanword))

    def test_a_feminine_noun_in_ост_gets_its_second_т_first(self) -> None:
        for wrong, right in (("радоста", "радостта"), ("смърта", "смъртта")):
            with self.subTest(wrong=wrong):
                self.assertEqual(spelling.suggest(wrong)[0], right)

    def test_a_number_and_an_abbreviation_take_a_space(self) -> None:
        self.assertIn(("abbreviation_space", "1990г.", "1990 г."), fixes("До 1990г. нищо", gramoten.KIND_FORMAT))
        self.assertIn(("abbreviation_space", "5млн.", "5 млн."), fixes("Около 5млн. души", gramoten.KIND_FORMAT))
        self.assertEqual(
            [f for f in fixes("През 1990 г. и 5 млн. души", gramoten.KIND_FORMAT) if f[0] == "abbreviation_space"], []
        )

    def test_a_day_before_the_month_has_no_leading_zero(self) -> None:
        self.assertIn(("date_leading_zero", "02", "2"), fixes("На 02 октомври 2020", gramoten.KIND_FORMAT))
        self.assertEqual(
            [f for f in fixes("На 2 октомври и на 02.10.2020", gramoten.KIND_FORMAT) if f[0] == "date_leading_zero"], []
        )

    def test_correct_compounds_and_counts_stay_quiet(self) -> None:
        self.assertEqual([i.code for i in gramoten.check("на едноименната провинция, 100-на активисти")], [])


class DictionarySource(unittest.TestCase):
    """Misspellings the dictionary must not accept (tools/bg_BG/SOURCE.md)."""

    def test_dictionary_misspellings_are_flagged(self):
        for wrong, right in {
            "подтискам": "потискам",
            "прахуляк": "прахоляк",
            "отверка": "отвертка",
            "уречна": "уречена",
        }.items():
            with self.subTest(wrong):
                self.assertFalse(spelling.is_correct(wrong))
                self.assertIn(right, spelling.suggest(wrong))
                self.assertTrue(spelling.is_correct(right))

    def test_nepriyazan_has_its_feminine_forms(self):
        for word in ("неприязън", "неприязънта", "неприязни", "неприязните"):
            self.assertTrue(spelling.is_correct(word), word)
        self.assertFalse(spelling.is_correct("неприязънът"))


if __name__ == "__main__":
    unittest.main()


class DictionaryErrata(unittest.TestCase):
    def test_the_own_corrections_override_the_dictionary(self) -> None:
        for wrong, right in {"подтиснат": "потиснат", "подтисничество": "потисничество"}.items():
            with self.subTest(wrong=wrong):
                self.assertFalse(spelling.is_correct(wrong))
                self.assertEqual(spelling.suggest(wrong)[0], right)
                self.assertNotIn(wrong, spelling.suggest(right[:-1] + "x"))

    def test_both_standard_spellings_of_a_word_are_accepted(self) -> None:
        """пинцет (м.), пинцета and пинсета (ж.) are all standard, мн. пинцети."""
        for word in ("пинцет", "пинцетът", "пинцета", "пинцетата", "пинсета", "пинсетата", "пинцети", "пинсети"):
            with self.subTest(word=word):
                self.assertTrue(spelling.is_correct(word))
