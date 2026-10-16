"""Source contract for :mod:`workbench.collect_engineering_scale`.

Each university's faculty directory gets its own module in this package, because
the page structures differ enough that one shared template cannot parse them all.

A source module must expose exactly two names:

``SPECS``
    A tuple of ``dict`` describing where the directory lives and which discipline
    its teachers belong to::

        SPECS = ({
            "key": "example_control",          # unique, stable identifier
            "code": "0811",                    # 4-digit 2022 first-level discipline code
            "institution": "示例大学",
            "department": "自动化学院",          # used when a row has no finer unit
            "discipline": "控制科学与工程",       # human-readable name (for messages)
            "listing": "https://.../szdw.htm",  # the directory page
            "max_pages": 1,                     # how many pages to walk (1 if single page)
        },)

``parse(html, url, spec)``
    Returns a list of mentor rows for one listing page.

Rules a parser must follow (these are project red lines, not style preferences):

1. **No email, no phone.** Never copy a contact field into a row. The project does
   not store contact information at all.
2. **No invented data.** If the directory does not state a research direction,
   leave it as :data:`workbench.collect_thin_discipline_depth.NO_DIRECTION`
   (``"方向待补"``). Never put a 职称 such as ``教授`` into the direction field —
   a rank is not a direction.
3. **Every row cites its source.** Use
   :func:`workbench.collect_thin_discipline_depth.roster_row`, which records the
   exact listing URL, and pass the person's own page as ``homepage`` when the
   directory links to one.
4. **Names must be real people.** ``roster_row`` validates the name against
   ``NAME_RE``; navigation text, office names and 研究所 headings must be filtered
   out before that call, not passed through and hoped for.
5. **Skip non-teaching units** such as 党委 / 工会 / 离退休 / 办公室. Research
   institutes, key laboratories and collaborative centres are legitimate and stay.

Testing a source module
-----------------------
Save a real listing page to ``workbench/tests/fixtures/<key>.html`` and assert the
parser finds the expected people, e.g.::

    from workbench.sources.<module> import parse, SPECS
    rows = parse(pathlib.Path("fixture.html").read_text(encoding="utf-8"),
                 SPECS[0]["listing"], SPECS[0])
    assert rows and all(r["name"] for r in rows)

The collector is responsible for fetching, de-duplicating and merging; a source
module only parses.
"""

from __future__ import annotations

CONTRACT_VERSION = 1
