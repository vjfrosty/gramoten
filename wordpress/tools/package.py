"""The plugin's zip, for WordPress.org or for uploading to a site.

    python wordpress/tools/package.py

Run `npm run build` and `tools/build_data.py` first. Fails when the zip is over the
directory's limit of 10 MB, or when a file it needs is missing.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
OUT = ROOT / "gramoten.zip"
LIMIT = 10_000_000
REQUIRED = ("gramoten.php", "readme.txt", "LICENSE", "NOTICE", "build/editor.js", "build/worker.js", "data/bg_forms.marisa")


def main() -> int:
    missing = [name for name in REQUIRED if not (PLUGIN / name).exists()]
    if missing:
        print(f"Missing: {', '.join(missing)}", file=sys.stderr)
        return 1
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(PLUGIN.rglob("*")):
            if path.is_file():
                archive.write(path, Path("gramoten") / path.relative_to(PLUGIN))
    size = OUT.stat().st_size
    print(f"{OUT.name}: {size / 1e6:.2f} MB (limit {LIMIT / 1e6:.0f} MB)")
    if size >= LIMIT:
        print("Over the WordPress.org limit.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
