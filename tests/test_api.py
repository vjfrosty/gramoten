"""The public API, messages, speed, the command line and the test page."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT

import gramoten
from gramoten import spelling, tokenize


class ApplyFixes(unittest.TestCase):
    TEXT = "Знаем че 5-ти май е 19 годишен празник  - до сега."

    def test_one_pass_skips_an_overlapping_fix(self):
        # The double space sits inside ` - `: the dash waits for the next check.
        fixed = gramoten.apply_fixes(self.TEXT, gramoten.check(self.TEXT))
        self.assertEqual(fixed, "Знаем, че 5 май е 19-годишен празник - досега.")

    def test_fix_text_checks_again_until_done(self):
        self.assertEqual(gramoten.fix_text(self.TEXT), "Знаем, че 5 май е 19-годишен празник – досега.")

    def test_spelling_is_never_changed(self):
        text = "Тва е напсиано."
        self.assertEqual(gramoten.apply_fixes(text, gramoten.check(text)), text)

    def test_codes_limit_it(self):
        fixed = gramoten.apply_fixes(self.TEXT, gramoten.check(self.TEXT), codes={"double_space"})
        self.assertEqual(fixed, self.TEXT.replace("  ", " "))

    def test_stale_and_overlapping_issues_are_skipped(self):
        a = gramoten.Issue("x", 0, 3, "abc", fix="A")
        b = gramoten.Issue("y", 2, 5, "cde", fix="C")  # overlaps a
        c = gramoten.Issue("z", 6, 7, "q", fix="Q")  # text is "g" there: stale
        self.assertEqual(gramoten.apply_fixes("abcdefg", [b, a, c]), "Adefg")


class BulgarianMessages(unittest.TestCase):
    def test_every_rule_message_has_a_bulgarian_entry(self):
        # Every message a rule can write, read from the source: a new rule without
        # an entry in messages_bg.py fails here. An f-string's parts become "X".
        import ast

        from gramoten import messages_bg

        def literal(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                return node.value
            if isinstance(node, ast.JoinedStr):
                return "".join(v.value if isinstance(v, ast.Constant) else "X" for v in node.values)
            return None

        messages = set()
        for path in (ROOT / "src" / "gramoten").glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    index = {"Hit": 3, "Issue": 7}.get(node.func.id)
                    if index is not None and len(node.args) > index:
                        message = literal(node.args[index])
                        if message:
                            messages.add(message)
        self.assertGreater(len(messages), 40)
        missing = sorted(m for m in messages if not messages_bg.known(m))
        self.assertEqual(missing, [])

    def test_check_fills_message_bg(self):
        issues = {i.code: i for i in gramoten.check("Знаем че до сега.  Край")}
        self.assertEqual(issues["comma_before_conjunction"].message_bg, "Запетая пред „че“")
        self.assertEqual(issues["written_together"].message_bg, "Пише се слято: „досега“")
        self.assertEqual(issues["double_space"].message_bg, "Повече от един интервал")
        self.assertEqual(issues["double_space"].to_json()["message_bg"], "Повече от един интервал")

    def test_unknown_message_stays_english(self):
        from gramoten import messages_bg

        self.assertEqual(messages_bg.bulgarian("Something new"), "Something new")


class Speed(unittest.TestCase):
    """The shortcuts that keep a check fast find what the slow way finds."""

    def test_a_long_text_finds_what_its_last_paragraph_finds(self) -> None:
        paragraph = "Ще дойда утре но не знам кога. Купих хляб който беше пресен. Имаше 5 човека и й казах."
        lead = "Първо изречение. " * 40
        shift = len(lead)
        alone = [(i.code, i.start + shift, i.end + shift, i.fix) for i in gramoten.check(paragraph)]
        inside = [(i.code, i.start, i.end, i.fix) for i in gramoten.check(lead + paragraph) if i.start >= shift]
        self.assertTrue(alone)
        self.assertEqual(inside, alone)

    def test_the_two_edit_search_is_limited_by_a_count_of_words(self) -> None:
        from unittest import mock

        text = "интрнет и интрнет."
        with mock.patch.object(gramoten, "DEEP_SUGGESTIONS_PER_CALL", 1):
            first, second = (len(i.suggestions) for i in gramoten.check(text))
            self.assertEqual((first, second), (5, 2))
            self.assertEqual(
                [i.suggestions for i in gramoten.check(text)], [i.suggestions for i in gramoten.check(text)]
            )

    def test_two_edit_words_fill_up_after_the_one_edit_words(self) -> None:
        self.assertEqual(spelling.suggest("интрнет", deep=False), ["интернет", "интранет"])
        filled = spelling.suggest("интрнет")
        self.assertEqual(filled[:2], ["интернет", "интранет"])
        self.assertEqual(len(filled), 5)

    def test_the_two_edit_search_finds_every_word_two_edits_away(self) -> None:
        forms = spelling._forms()

        def opens(prefix: str) -> bool:
            return next(forms.iterkeys(prefix), None) is not None

        for word in ("интрнет", "преоцнени", "консулатант"):
            with self.subTest(word=word):
                by_editing = {w for first in spelling._edits(word) for w in spelling._edits(first) if w in forms}
                walked, finished = spelling._within_two(word, opens, forms.__contains__, float("inf"))
                self.assertTrue(finished)
                self.assertEqual(walked, by_editing)

    def test_pruned_suggestions_still_reach_two_edits(self) -> None:
        from unittest import mock

        with mock.patch.object(spelling, "SECOND_EDIT_STEPS", 10**9):  # the whole search
            self.assertIn("интернет", spelling._search("интренетт", frozenset(), True)[0])
            self.assertEqual(spelling._search("офретта", frozenset(), True)[0][0], "оферта")

    def test_a_search_cut_short_is_not_kept(self) -> None:
        from unittest import mock

        key = ("интренетт", frozenset(), True)
        spelling.clear_suggestions()
        with mock.patch.object(spelling, "SECOND_EDIT_STEPS", 0):  # cut after the first step
            spelling._ranked(*key)
        self.assertNotIn(key, spelling._RANKED)
        with mock.patch.object(spelling, "SECOND_EDIT_STEPS", 10**9):
            self.assertIn("интернет", spelling._ranked(*key))
        self.assertIn(key, spelling._RANKED)

    def test_the_cache_keeps_the_most_recent_words(self) -> None:
        from unittest import mock

        spelling.clear_suggestions()
        with mock.patch.object(spelling, "_RANKED_MAX", 2):
            for word in ("офрета", "клиентте", "абонамнт"):
                spelling._ranked(word, frozenset(), False)
        self.assertEqual([k[0] for k in spelling._RANKED], ["клиентте", "абонамнт"])

    def test_a_window_keeps_the_start_of_a_text(self) -> None:
        self.assertEqual(tokenize.before("ab", 2), "ab")
        long = "." * 500
        self.assertNotRegex(tokenize.before(long, 500), r"^\W*$")


class CommandLine(unittest.TestCase):
    def run_cli(self, *argv, stdin=None):
        import contextlib
        import io

        from gramoten.__main__ import main

        out, err = io.StringIO(), io.StringIO()
        old_stdin = sys.stdin
        if stdin is not None:
            sys.stdin = io.TextIOWrapper(io.BytesIO(stdin.encode("utf-8")), encoding="utf-8")
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = main(list(argv))
        finally:
            sys.stdin = old_stdin
        return code, out.getvalue(), err.getvalue()

    def write(self, text):
        d = tempfile.mkdtemp()
        path = Path(d) / "t.txt"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_findings_exit_one_with_line_and_column(self):
        code, out, _ = self.run_cli(self.write("Добър ден.\nЗнаем че е така."))
        self.assertEqual(code, 1)
        self.assertIn("t.txt:2:6: punctuation comma_before_conjunction:", out)
        self.assertIn("Запетая пред „че“", out)

    def test_clean_text_exits_zero(self):
        code, out, _ = self.run_cli("check", self.write("Добър ден."))
        self.assertEqual((code, out), (0, ""))

    def test_english_messages(self):
        _, out, _ = self.run_cli("--lang", "en", self.write("Знаем че е така."))
        self.assertIn("Comma before „че“", out)

    def test_json(self):
        import json

        code, out, _ = self.run_cli("--json", stdin="Знаем че е така.")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)[0]["code"], "comma_before_conjunction")

    def test_fix_prints_fixed_text(self):
        code, out, _ = self.run_cli("--fix", stdin="Знаем че до сега.")
        self.assertEqual((code, out), (0, "Знаем, че досега."))

    def test_fix_keeps_the_line_endings_of_the_file(self):
        import os
        import subprocess

        for newline in (b"\n", b"\r\n"):
            with self.subTest(newline=newline):
                path = Path(tempfile.mkdtemp()) / "text.txt"
                path.write_bytes("Знаем че.".encode() + newline + "До сега.".encode() + newline)
                env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
                out = subprocess.run(
                    [sys.executable, "-m", "gramoten", "--fix", str(path)], capture_output=True, env=env
                ).stdout
                self.assertEqual(out, "Знаем, че.".encode() + newline + "Досега.".encode() + newline)

    def test_own_words_from_a_file(self):
        """Names an app's texts use stay out of the package: `--words` adds them per run."""
        import json

        text = self.write("Кукушев ще води.")
        self.assertEqual(self.run_cli(text)[0], 1)
        plain = Path(tempfile.mkdtemp()) / "names.txt"
        plain.write_text("# our names" + chr(10) + "Кукушев" + chr(10), encoding="utf-8")
        self.assertEqual(self.run_cli("--words", str(plain), text)[0], 0)
        store = Path(tempfile.mkdtemp()) / "words.json"
        store.write_text(json.dumps({"words": {"кукушев": {"by": "x", "at": "t"}}}), encoding="utf-8")
        self.assertEqual(self.run_cli("--words", str(store), text)[0], 0)

    def test_missing_file_exits_two(self):
        code, _, err = self.run_cli(str(Path(tempfile.mkdtemp()) / "none.txt"))
        self.assertEqual(code, 2)
        self.assertIn("none.txt", err)


class Playground(unittest.TestCase):
    def test_page_and_check(self):
        import json
        import threading
        import urllib.error
        import urllib.request
        from http.server import ThreadingHTTPServer

        from gramoten import server

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        try:
            with urllib.request.urlopen(base + "/") as r:
                self.assertIn("Правопис", r.read().decode("utf-8"))
            body = json.dumps({"text": "Знаем че е така.", "extra": []}).encode("utf-8")
            with urllib.request.urlopen(urllib.request.Request(base + "/check", body)) as r:
                issues = json.loads(r.read())["issues"]
            self.assertEqual(issues[0]["message_bg"], "Запетая пред „че“")
            body = json.dumps({"text": "Знаем че до  сега."}).encode("utf-8")
            with urllib.request.urlopen(urllib.request.Request(base + "/fix", body)) as r:
                self.assertEqual(json.loads(r.read())["text"], "Знаем, че досега.")
            with self.assertRaises(urllib.error.HTTPError) as bad:
                urllib.request.urlopen(urllib.request.Request(base + "/check", "Знаем".encode("cp1251")))
            self.assertEqual(bad.exception.code, 400)
        finally:
            httpd.shutdown()
            httpd.server_close()
