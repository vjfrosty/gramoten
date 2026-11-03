"""Fonts an e-mail asks for and a reader will not get."""

from __future__ import annotations

import unittest

from gramoten import fonts


class Fonts(unittest.TestCase):
    def test_pasted_and_unloaded_fonts(self) -> None:
        html = (
            "<style>p{font-family: Verdana, sans-serif}</style>"
            '<p style="font-family: &quot;Brand Sans&quot;, Verdana, sans-serif">а</p>'
            '<p style="font-family: BrandSans, Verdana, sans-serif">б</p>'
            '<p style="font-family: +mn-ea">в</p>'
            '<font face="Verdana">г</font>'
            '<p style="font-family: Calibri, sans-serif">д</p>'
        )
        rows = {
            (r["code"], r["family"], r["count"]) for r in fonts.group(fonts.check(html, house=frozenset({"verdana"})))
        }
        self.assertIn(("font_not_loaded", "Brand Sans", 1), rows)
        self.assertIn(("font_not_loaded", "BrandSans", 1), rows)
        self.assertIn(("font_name_variant", "Brand Sans", 1), rows)
        self.assertIn(("font_office_leak", "+mn-ea", 1), rows)
        self.assertIn(("font_no_fallback", "+mn-ea", 1), rows)
        self.assertIn(("font_legacy_tag", "Verdana", 1), rows)
        self.assertIn(("font_mismatch", "Calibri", 1), rows)
        self.assertNotIn("font_mismatch", {code for code, family, _ in rows if family == "Verdana"})

    def test_a_declared_web_font_loads(self) -> None:
        html = '<style>@font-face{font-family: BrandSerif; src: url(x.woff)}</style><p style="font-family: BrandSerif, serif">а</p>'
        self.assertEqual(fonts.check(html, house=frozenset({"brandserif"})), [])
