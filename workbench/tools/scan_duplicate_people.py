"""Scan the workbench catalogue for duplicate people and ambiguous identities.

Two different problems get confused, so they are reported separately:

**Duplicates (a bug).** The same person recorded twice under the *same*
``(institution, department, name)`` key. The merge functions key on that triple, so
this should never happen; it indicates a parser produced two different department
strings for one person, or a merge key drifted between runs.

**Cross-appointments (by design).** The same person listed under *different*
departments at one institution, e.g. a joint appointment between 材料科学与工程学院
and 化学化工学院. The project keeps these as separate rows on purpose, because the
department is part of the identity the user is checking. They are reported so the
behaviour is visible and so a real duplicate can be told apart from a deliberate
one. In the engineering scope a cross-appointment is still counted once, through
its engineering discipline code.

Usage:
    .venv\\Scripts\\python.exe workbench\\tools\\scan_duplicate_people.py
"""

from __future__ import annotations

import pathlib
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from workbench import catalog  # noqa: E402


def main() -> int:
    catalog.static_catalog.cache_clear()
    entries = catalog.static_catalog()[0]

    keyed: dict[tuple, list] = defaultdict(list)
    for p in entries:
        keyed[(p.get("institution", ""), p.get("department", ""), p.get("name", ""))].append(p)
    duplicates = {k: v for k, v in keyed.items() if len(v) > 1}

    identity: dict[tuple, list] = defaultdict(list)
    for p in entries:
        identity[(p.get("institution", ""), p.get("name", ""),
                  (p.get("homepage") or "").strip())].append(p)
    cross = {k: v for k, v in identity.items()
             if len(v) > 1 and len({x.get("department", "") for x in v}) > 1}

    print(f"catalogue entries: {len(entries)}")
    print(f"duplicates on (institution, department, name): {len(duplicates)}")
    for (inst, dept, name), rows in list(duplicates.items())[:20]:
        print(f"  {name} @ {inst} / {dept}  ({len(rows)} rows)")
        for p in rows:
            print(f"      id={p['id'][:26]} origin={p.get('origin','')!r}")

    print()
    print(f"cross-department identities (same institution+name+homepage): {len(cross)}")
    for (inst, name, hp), rows in list(cross.items())[:20]:
        depts = "、".join(sorted({x.get("department", "") for x in rows}))
        print(f"  {name} @ {inst}: {depts}")

    print()
    if duplicates:
        print("RESULT: duplicates found — the merge key is drifting; investigate before publishing.")
        return 1
    print("RESULT: no duplicates on the merge key. Cross-appointments listed above are by design.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
