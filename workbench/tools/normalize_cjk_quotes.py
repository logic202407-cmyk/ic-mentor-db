"""Convert ASCII double quotes around CJK text to Chinese typographic quotes.

Straight quotes mixed into Chinese prose look like typos in a printed report.
This rewrites paired ASCII double quotes to “ ” only when the enclosed span or
its immediate neighbourhood contains CJK characters, so code and identifiers are
left untouched. Fenced code blocks are skipped entirely.
"""

from __future__ import annotations

import pathlib
import re
import sys

CJK = re.compile(r"[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uff00-\uffef]")


def convert(text: str) -> tuple[str, int]:
    out_lines = []
    changed = 0
    in_fence = False
    for line in text.split("\n"):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        if in_fence:
            out_lines.append(line)
            continue

        # Protect inline code spans from quote rewriting.
        spans: list[str] = []

        def stash(m: re.Match) -> str:
            spans.append(m.group(0))
            return f"\x00{len(spans) - 1}\x00"

        protected = re.sub(r"`[^`]*`", stash, line)

        def repl(m: re.Match) -> str:
            nonlocal changed
            inner = m.group(1)
            ctx = protected[max(0, m.start() - 12):m.end() + 12]
            # Only convert when CJK is inside the quotes or right around them.
            if not (CJK.search(inner) or CJK.search(ctx)):
                return m.group(0)
            changed += 1
            return "\u201c" + inner + "\u201d"

        protected = re.sub(r'"([^"\n]{0,200})"', repl, protected)
        for i, span in enumerate(spans):
            protected = protected.replace(f"\x00{i}\x00", span)
        out_lines.append(protected)

    return "\n".join(out_lines), changed


def main() -> int:
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        return 2
    for p in paths:
        path = pathlib.Path(p)
        text = path.read_text(encoding="utf-8")
        new, n = convert(text)
        if n:
            path.write_text(new, encoding="utf-8")
        print(f"{path}: {n} quoted span(s) converted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
