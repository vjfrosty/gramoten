"""Шрифтове: the fonts an e-mail asks for, and the ones a reader will not get.

This reads an e-mail's HTML and reports, by rule, with no network:

| Code | Finding |
|---|---|
| `font_not_loaded` | The first family of a stack is no common system font and no `@font-face` in the document declares it, so nobody sees it (a brand font, futuraBookRegular, Calibri). |
| `font_office_leak` | An Office theme font (`+mn-ea`, `+mj-lt`) pasted in from Word or Outlook. |
| `font_no_fallback` | A stack that ends with no generic family (`sans-serif`, `serif`). |
| `font_name_variant` | One family under two names (`BrandSans`, `Brand Sans`). |
| `font_legacy_tag` | A `<font face>` tag. |
| `font_mismatch` | Text in a font the template itself never uses (Calibri pasted from Word). |

**The template's fonts are the reference.** No house font is assumed. The
host passes `house`, the families its template uses (`families_in`); text in
any other family is a mismatch. Without `house`, the body font is the
reference: a rule for `p` or `td` in a `<style>` block, otherwise the
`<body>` tag's. The body font alone flags every template heading, so a host
with a template should pass `house`. Glyph coverage (does a web font have Cyrillic?) needs the font
files and is not checked: nothing is fetched.

`check(html)` returns one `FontFinding` per occurrence, with its offset in the
HTML; a host groups them as it shows them (`group`).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from html import unescape

#: Fonts every mail client's platform has, or maps to one it has.
SYSTEM_FONTS = frozenset(
    {
        "arial",
        "helvetica",
        "helvetica neue",
        "verdana",
        "georgia",
        "tahoma",
        "trebuchet ms",
        "times new roman",
        "times",
        "courier new",
        "courier",
        "segoe ui",
        "lucida grande",
        "lucida sans unicode",
        "palatino",
        "palatino linotype",
        "garamond",
        "book antiqua",
        "geneva",
        "roboto",
        "-apple-system",
        "blinkmacsystemfont",
        "system-ui",
        "monaco",
        "consolas",
    }
)
GENERIC = frozenset({"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui"})

NOT_LOADED = "font_not_loaded"
OFFICE_LEAK = "font_office_leak"
NO_FALLBACK = "font_no_fallback"
NAME_VARIANT = "font_name_variant"
LEGACY_TAG = "font_legacy_tag"
MISMATCH = "font_mismatch"

CODES = (NOT_LOADED, OFFICE_LEAK, NO_FALLBACK, NAME_VARIANT, LEGACY_TAG, MISMATCH)

_DECLARATION = re.compile(r"font-family\s*:\s*([^;\"}<>]+?)\s*(?=;|\"|}|<|$)", re.I)
_FONT_TAG = re.compile(r"<font\b[^>]*\bface\s*=\s*(?:\"([^\"]*)\"|'([^']*)')", re.I)
_FACE_RULE = re.compile(r"@font-face\s*{([^}]*)}", re.I)
_STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style\s*>", re.I | re.S)
_RULE = re.compile(r"([^{}@]+){([^{}]*)}")
_BODY_TAG = re.compile(r"<body\b[^>]*\bstyle\s*=\s*\"([^\"]*)\"", re.I)
_COMMENT = re.compile(r"<!--(?!\[if\b).*?-->", re.S)


@dataclass(frozen=True)
class FontFinding:
    code: str
    offset: int
    #: The family the finding is about, as written (`BrandSans`).
    family: str
    #: The whole stack, as written.
    stack: str
    message: str


def _quotes(html: str) -> str:
    """`&quot;` and `&#39;` as one quote and spaces: same length, so offsets hold, and no `;` cuts a stack."""
    return html.replace("&quot;", "'     ").replace("&#34;", "'    ").replace("&#39;", "'    ")


def families(stack: str) -> list[str]:
    """`"Brand Sans", Verdana, sans-serif !important` -> `["Brand Sans", "Verdana", "sans-serif"]`."""
    stack = unescape(stack).replace("!important", "")
    # A style missing its `;` runs on into the next property: `Arial font-size:12px`.
    stack = re.split(r"\s[a-z-]+\s*:", stack, maxsplit=1)[0]
    return [name.strip().strip("\"'").strip() for name in stack.split(",") if name.strip().strip("\"'").strip()]


def _key(name: str) -> str:
    return re.sub(r"[\s_-]+", "", name.lower())


def declared_faces(html: str) -> frozenset[str]:
    """Every family an `@font-face` rule in the document declares, by key."""
    found: set[str] = set()
    for rule in _FACE_RULE.finditer(_quotes(html)):
        for decl in _DECLARATION.finditer(rule.group(1)):
            found.update(_key(name) for name in families(decl.group(1)))
    return frozenset(found)


def body_stack(html: str) -> list[str]:
    """The text font list the document sets: a `p`/`td` rule in a `<style>` block, else `<body style>`.

    A rule inside an Outlook-only `<!--[if mso]>` block counts: a template may
    state its text font only there and write it inline in the content. `[]`
    when nothing says.
    """
    html = _quotes(html)
    for block in _STYLE_BLOCK.finditer(html):
        css = re.sub(r"/\*.*?\*/", "", block.group(1), flags=re.S)
        for rule in _RULE.finditer(css):
            selectors = {s.strip().lower() for s in rule.group(1).split(",")}
            decl = _DECLARATION.search(rule.group(2))
            if decl and selectors & {"p", "td"}:
                names = families(decl.group(1))
                if names:
                    return names
    body = _BODY_TAG.search(html)
    decl = _DECLARATION.search(body.group(1)) if body else None
    return families(decl.group(1)) if decl else []


def body_family(html: str) -> str | None:
    """The first family of `body_stack`."""
    names = body_stack(html)
    return names[0] if names else None


def _uses(html: str) -> list[tuple[int, str, bool]]:
    """`(offset, stack, is_font_tag)` for every font declaration outside comments and `@font-face`."""
    masked = _COMMENT.sub(lambda m: " " * len(m.group(0)), _quotes(html))
    masked = _FACE_RULE.sub(lambda m: " " * len(m.group(0)), masked)
    uses = [(m.start(1), m.group(1), False) for m in _DECLARATION.finditer(masked)]
    uses += [(m.start(), m.group(1) or m.group(2) or "", True) for m in _FONT_TAG.finditer(masked)]
    return sorted(uses)


def families_in(html: str) -> frozenset[str]:
    """The first family of every font declaration in `html`, as keys for `house`."""
    return frozenset(_key(families(stack)[0]) for _, stack, _ in _uses(html) if families(stack))


def check(html: str, *, house: frozenset[str] | None = None) -> list[FontFinding]:
    """Every font finding in `html`. `house`: the families (`families_in`) text may use."""
    faces = declared_faces(html)
    reference = body_family(html)
    allowed = house if house is not None else frozenset({_key(reference)} if reference else ())
    found: list[FontFinding] = []
    spellings: dict[str, Counter[str]] = {}
    for offset, stack, tag in _uses(html):
        names = families(stack)
        if not names:
            continue
        first = names[0]
        spellings.setdefault(_key(first), Counter())[first] += 1
        if tag:
            found.append(
                FontFinding(
                    LEGACY_TAG, offset, first, stack, "An old <font face> tag; set the font in the text's style."
                )
            )
        if first.startswith(("+mn-", "+mj-")):
            found.append(
                FontFinding(
                    OFFICE_LEAK,
                    offset,
                    first,
                    stack,
                    f"“{first}” is an Office theme font pasted in from Word or Outlook.",
                )
            )
        elif _key(first) not in faces and first.lower() not in SYSTEM_FONTS and first.lower() not in GENERIC:
            found.append(
                FontFinding(
                    NOT_LOADED,
                    offset,
                    first,
                    stack,
                    f"“{first}” is not loaded by this e-mail and is not a common system font: "
                    f"readers see {_fallback(names, faces)} instead.",
                )
            )
        if not any(name.lower() in GENERIC for name in names):
            found.append(
                FontFinding(NO_FALLBACK, offset, first, stack, "The font list ends without sans-serif or serif.")
            )
        if allowed and _key(first) not in allowed and first.lower() not in GENERIC and not tag:
            found.append(
                FontFinding(
                    MISMATCH,
                    offset,
                    first,
                    stack,
                    f"“{first}” is not one of the template's fonts"
                    + (f"; its text font is {reference}." if reference else "."),
                )
            )
    for key, variants in spellings.items():
        if len(variants) > 1:
            written = sorted(variants)
            offset = next(o for o, s, _ in _uses(html) if families(s) and _key(families(s)[0]) == key)
            found.append(
                FontFinding(
                    NAME_VARIANT,
                    offset,
                    written[0],
                    ", ".join(written),
                    "One font under " + " and ".join(f"“{n}”" for n in written) + ".",
                )
            )
    return sorted(found, key=lambda f: (f.offset, f.code))


def _fallback(names: list[str], faces: frozenset[str]) -> str:
    for name in names[1:]:
        if name.lower() in SYSTEM_FONTS or _key(name) in faces:
            return name
        if name.lower() in GENERIC:
            return f"the client's {name}"
    return "the client's default font"


def group(findings: list[FontFinding]) -> list[dict]:
    """One row per (code, family): its first offset and how many times it occurs."""
    rows: dict[tuple[str, str], dict] = {}
    for f in findings:
        row = rows.setdefault(
            (f.code, f.family),
            {
                "code": f.code,
                "family": f.family,
                "stack": f.stack,
                "message": f.message,
                "offset": f.offset,
                "count": 0,
            },
        )
        row["count"] += 1
    return list(rows.values())
