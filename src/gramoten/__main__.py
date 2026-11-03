"""The command line.

    python -m gramoten [check] [FILE ...]   check files, or standard input when none is given
    python -m gramoten serve                the local test page

`check` exits 0 when nothing is found, 1 when something is, 2 on an error, so it
fits scripts, pre-commit hooks and CI. Run `python -m gramoten check --help`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import gramoten
from gramoten.words import load_words

EXIT_CLEAN, EXIT_FOUND, EXIT_ERROR = 0, 1, 2


def _read(path: str) -> str:
    """A file, or standard input for `-`, as UTF-8 (a byte-order mark is dropped)."""
    data = sys.stdin.buffer.read() if path == "-" else Path(path).read_bytes()
    return data.decode("utf-8-sig")


def _position(text: str, offset: int) -> tuple[int, int]:
    """1-based line and column of a character offset."""
    line = text.count("\n", 0, offset) + 1
    return line, offset - (text.rfind("\n", 0, offset) + 1) + 1


def _shown(s: str) -> str:
    """Line breaks and spaces made visible, so a whitespace finding can be seen."""
    return s.replace("\n", "\u21b5").replace(" ", "\u237d").replace("\u00a0", "\u2423")


def _line(name: str, text: str, issue: gramoten.Issue, lang: str) -> str:
    line, col = _position(text, issue.start)
    message = issue.message_bg if lang == "bg" else issue.message
    out = f"{name}:{line}:{col}: {issue.kind} {issue.code}: „{_shown(issue.text)}“ – {message}"
    if issue.fix is not None:
        out += f" → „{_shown(issue.fix)}“"
    elif issue.suggestions:
        out += " → " + ", ".join(issue.suggestions)
    return out


def check(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="python -m gramoten check",
        description="Check Bulgarian text for spelling, punctuation, grammar and format. "
        "Exit status: 0 nothing found, 1 findings, 2 error.",
    )
    p.add_argument("files", nargs="*", metavar="FILE", help="UTF-8 text files; none or - reads standard input")
    p.add_argument("--json", action="store_true", help="print the findings as JSON")
    p.add_argument(
        "--fix",
        action="store_true",
        help="print the text with every certain fix applied instead of the findings (one input only)",
    )
    p.add_argument("--extra", default="", metavar="WORDS", help="comma-separated words to accept as correct")
    p.add_argument(
        "--words",
        action="append",
        default=[],
        metavar="FILE",
        help="your own words to accept (names, brands): one per line, or a WordStore .json; repeatable",
    )
    p.add_argument("--lang", choices=("bg", "en"), default="bg", help="language of the messages (default bg)")
    p.add_argument("--all", action="store_true", help="also show quiet findings (such as non-breaking spaces)")
    args = p.parse_args(argv)

    files = args.files or ["-"]
    if args.fix and len(files) != 1:
        p.error("--fix takes one input")
    extra = frozenset(w.strip().lower() for w in args.extra.split(",") if w.strip())
    for path in args.words:
        try:
            extra |= load_words(path)
        except (OSError, UnicodeDecodeError, ValueError) as e:
            print(f"gramoten: {path}: {e}", file=sys.stderr)
            return EXIT_ERROR

    results: dict[str, tuple[str, list[gramoten.Issue]]] = {}
    for path in files:
        try:
            text = _read(path)
        except (OSError, UnicodeDecodeError) as e:
            print(f"gramoten: {path}: {e}", file=sys.stderr)
            return EXIT_ERROR
        results["<stdin>" if path == "-" else path] = (text, [] if args.fix else gramoten.check(text, extra))

    if args.fix:  # fix_text checks again itself
        ((text, _),) = results.values()
        fixed = gramoten.fix_text(text, extra)
        # As bytes, so the text keeps its own line endings: text mode on Windows
        # would turn the `\r\n` of a Windows file into `\r\r\n`.
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.flush()
            sys.stdout.buffer.write(fixed.encode("utf-8"))
            sys.stdout.buffer.flush()
        else:
            sys.stdout.write(fixed)
        return EXIT_CLEAN

    found = 0
    if args.json:
        out = {name: [i.to_json() for i in issues if args.all or not i.quiet] for name, (_, issues) in results.items()}
        found = sum(len(v) for v in out.values())
        print(
            json.dumps(out if len(files) > 1 or args.files else next(iter(out.values())), ensure_ascii=False, indent=2)
        )
    else:
        for name, (text, issues) in results.items():
            for issue in issues:
                if args.all or not issue.quiet:
                    print(_line(name, text, issue, args.lang))
                    found += 1
    return EXIT_FOUND if found else EXIT_CLEAN


def serve(argv: list[str]) -> int:
    from .server import DEFAULT_PORT
    from .server import serve as run

    p = argparse.ArgumentParser(prog="python -m gramoten serve", description="Serve the local test page.")
    p.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"default {DEFAULT_PORT}")
    p.add_argument("--host", default="127.0.0.1", help="default 127.0.0.1 (this computer only)")
    p.add_argument("--open", action="store_true", help="open the page in the browser")
    args = p.parse_args(argv)
    try:
        run(args.port, args.host, args.open)
    except OSError as e:
        print(f"gramoten: cannot listen on {args.host}:{args.port}: {e}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_CLEAN


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "serve":
        return serve(argv[1:])
    if argv and argv[0] == "check":
        argv = argv[1:]
    return check(argv)


if __name__ == "__main__":
    sys.exit(main())
