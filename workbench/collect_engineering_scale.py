"""Widen the engineering corpus from university-wide public faculty directories.

Complements ``collect_thin_discipline_depth`` (which reads a single department
page per discipline) with sources that publish a per-discipline teacher list.
The first such source is the Beijing University of Science and Technology faculty
platform, whose discipline index lists every teacher with a personal homepage,
their 职称 and their 院系.

Contract, unchanged from the other collectors:

* every row records the exact listing URL it came from;
* the merge never overwrites an existing ``(institution, department, name)``;
* no email or phone number is stored;
* a missing research direction stays explicitly unknown rather than being filled
  with the 职称, which is a rank and not a direction.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

import requests
import urllib3
from bs4 import BeautifulSoup

from . import catalog
from . import public_research as research
from .collect_discipline_catalog import CODES, OUT, REFERENCE, aggregate
from .collect_thin_discipline_depth import COLLECTED_AT, NAME_RE, NO_DIRECTION, roster_row

urllib3.disable_warnings()

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
TIMEOUT = (10, 30)

# Per-university source modules live in ``workbench/sources/`` and are discovered
# at runtime by :func:`discover_sources`. See that package's docstring for the
# contract a source module must satisfy.


def fetch(url: str, attempts: int = 3, backoff: float = 1.5) -> str:
    """Fetch one page, retrying transient timeouts.

    The USTB platform intermittently stalls. Without a retry a single read timeout
    aborts that directory's pagination and silently truncates the roster (observed
    live: 242 rows dropping to 150), which would make the batch irreproducible.
    """
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            response = requests.get(url, headers=UA, timeout=TIMEOUT, verify=False)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            return response.text
        except Exception as exc:  # noqa: BLE001 - retry any transport error
            last = exc
            if attempt < attempts - 1:
                time.sleep(backoff * (attempt + 1))
    raise last  # type: ignore[misc]


def discover_sources() -> dict[str, dict]:
    """Load every source module in :mod:`workbench.sources`.

    Each module declares ``SPECS`` (where the directory lives and which discipline
    it belongs to) plus ``parse(html, url, spec)``. Adding a university means adding
    a module, not editing this collector.
    """
    import importlib
    import pkgutil

    from . import sources as sources_pkg

    found: dict[str, dict] = {}
    for info in pkgutil.iter_modules(sources_pkg.__path__):
        module = importlib.import_module(f"{sources_pkg.__name__}.{info.name}")
        parse = getattr(module, "parse", None)
        specs = getattr(module, "SPECS", None)
        if parse is None or not specs:
            continue
        for spec in specs:
            key = spec.get("key") or f"{info.name}:{spec.get('code')}"
            if key in found:
                raise ValueError(f"重复的来源 key：{key}")
            found[key] = {**spec, "parser": parse, "module": info.name}
    if not found:
        raise ValueError("workbench/sources 下没有可用的来源模块")
    return found


def collect(pages_per_source: int | None = None) -> tuple[list[dict], list[dict], list[dict]]:
    """Read every registered directory and return (rows, pages, failures)."""
    rows: list[dict] = []
    pages: list[dict] = []
    failures: list[dict] = []
    for key, spec in discover_sources().items():
        parser = spec["parser"]
        limit = pages_per_source or spec.get("max_pages", 1)
        seen: set[str] = set()
        for page_no in range(1, limit + 1):
            template = spec["listing"]
            url = template.format(page=page_no) if "{page}" in template else template
            try:
                html = fetch(url)
            except Exception as exc:  # noqa: BLE001
                failures.append({"source": key, "url": url,
                                 "error": f"{type(exc).__name__}: {exc}"})
                break
            pages.append({"url": url, "collected_at": COLLECTED_AT})
            parsed = parser(html, url, spec)
            fresh = [r for r in parsed if r["name"] not in seen]
            if not fresh:
                break
            for r in fresh:
                seen.add(r["name"])
            rows.extend(fresh)
            if "{page}" not in template:
                break
            if len(parsed) < 5:  # last page
                break

    unique: dict[tuple, dict] = {}
    for row in rows:
        unique.setdefault((row["institution"], row["department"], row["name"]), row)
    return list(unique.values()), pages, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="parse and report only")
    parser.add_argument("--enrich", action="store_true", help="read each new personal page")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    rows, pages, failures = collect()
    supplement = {
        "description": "工学规模扩充：北京科技大学教师主页学科索引（冶金工程）",
        "collected_at": COLLECTED_AT,
        "profiles": aggregate(rows),
        "pages": pages,
        "failures": failures,
    }
    for p in supplement["profiles"]:
        p["classification_basis"] = ("按学校教师主页的学科索引归入一级学科导航；"
                                     "不代替该教师所在机构的招生专业认定。")

    if args.dry_run:
        by_dept: dict[str, int] = {}
        for p in supplement["profiles"]:
            by_dept[p["department"]] = by_dept.get(p["department"], 0) + 1
        print(json.dumps({
            "profiles": len(supplement["profiles"]),
            "pages": len(pages),
            "failures": failures[:3],
            "by_department": by_dept,
        }, ensure_ascii=False, indent=1))
        return 0

    supplement_path = REFERENCE / "engineering_scale_faculty.json"
    # The upstream listing is occasionally flaky, so a re-run can parse far fewer
    # rows than a previous run. Never let such a run shrink the published
    # supplement, which is the reproduction artefact for this batch.
    #
    # `degraded` also gates the audit metadata: when the guard fires, the supplement
    # is the PREVIOUS file, so this run adds nothing and `added` would be written as 0.
    # That silently replaced a good run's "added: 746, failures: []" record with a
    # degraded one (observed 2026-10-15), so a degraded run must not overwrite the
    # audit's historical numbers.
    degraded = False
    previous_supplement = None
    if supplement_path.exists():
        try:
            previous_supplement = json.loads(supplement_path.read_text(encoding="utf8"))
        except (OSError, ValueError):
            previous_supplement = None
    if previous_supplement is not None:
        published = len(previous_supplement.get("profiles") or [])
        if len(supplement["profiles"]) < published:
            print(json.dumps({
                "warning": "本次解析结果少于已发布补充文件，保留原文件不覆盖",
                "parsed": len(supplement["profiles"]),
                "published": published,
                "failures": failures[:2],
            }, ensure_ascii=False), flush=True)
            supplement = previous_supplement
            degraded = True
    supplement_path.write_text(
        json.dumps(supplement, ensure_ascii=False, indent=2) + "\n", encoding="utf8")

    audit_path = REFERENCE / "engineering_scale_audit_20261015.json"
    previous = {}
    if audit_path.exists():
        try:
            previous = json.loads(audit_path.read_text(encoding="utf8"))
        except (OSError, ValueError):
            previous = {}
    before = previous.get("before") or {x["name"]: x["count"] for x in catalog.disciplines()}

    current = json.loads(OUT.read_text(encoding="utf8"))
    by_key = {(p["institution"], p["department"], p["name"]): p for p in current["profiles"]}
    added = 0
    for p in supplement["profiles"]:
        key = (p["institution"], p["department"], p["name"])
        if key in by_key:
            continue
        current["profiles"].append(p)
        by_key[key] = p
        added += 1
    for page in pages:
        if not any(p["url"] == page["url"] for p in current.get("pages", [])):
            current.setdefault("pages", []).append(page)
    OUT.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf8")

    catalog.static_catalog.cache_clear()
    after = {x["name"]: x["count"] for x in catalog.disciplines()}

    # Register identity sources so personal pages can be read.
    registry = dict(research.source_registry())
    selected = []
    for row in supplement["profiles"]:
        match = next((p for p in catalog.static_catalog()[0]
                      if all(p[k] == row[k] for k in ("institution", "department", "name"))), None)
        if match is None:
            continue
        selected.append(match["id"])
        reg = dict(registry.get(match["id"], {}))
        reg.update(name=match["name"], institution=match["institution"])
        if not reg.get("homepage"):
            reg.update(homepage=row["homepage"], identity_url=row["sources"][0]["url"],
                       source_kind="学校教师主页")
        registry[match["id"]] = reg
    research.SOURCE_REGISTRY.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    # The readable-domain allowlist and the registry reader are both cached. Without
    # clearing them, a school added in this run would still be treated as unreadable
    # and its personal pages would silently stay unenriched. Note that
    # source_registry() itself is uncached — only the two cached helpers below.
    research._registrable_domains.cache_clear()
    research._read_registry.cache_clear()

    audit = {
        "date": COLLECTED_AT,
        "scope": "工学规模扩充：北京科技大学 冶金工程（学校教师主页学科索引）",
        "first_recorded_at": previous.get("first_recorded_at", COLLECTED_AT),
        "before": before,
        "after": after,
        "profiles": len(supplement["profiles"]),
        "added": added,
        "profile_ids": selected,
        "pages": [p["url"] for p in pages],
        "failures": failures,
        "limits": [
            "来源为学校教师主页的学科索引，用于学科导航归类，不代表当年招生专业或名额。",
            "索引只给职称与院系，不含个人研究方向，故方向字段一律为“方向待补”。",
            "不收录邮箱、电话等联系方式。",
        ],
    }
    # A degraded run (guard fired) must not overwrite the audit's historical record:
    # it would replace "added: 746, failures: []" with "added: 0, failures: [SSLError…]"
    # even though nothing in the published data changed. Keep the previous numbers.
    if degraded and isinstance(previous.get("added"), int) and previous.get("added", 0) > added:
        audit = dict(previous)
        audit["last_degraded_run"] = {
            "date": COLLECTED_AT,
            "added": added,
            "failures": failures[:5],
            "note": "本次运行解析结果少于已发布补充文件，已保留原文件与原审计数字。",
        }
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf8")

    changed = {k: [before.get(k, 0), v] for k, v in after.items() if v != before.get(k, 0)}
    print(json.dumps({"profiles": len(supplement["profiles"]), "added": added,
                      "changes": changed}, ensure_ascii=False), flush=True)

    if args.enrich and selected:
        targets = selected[: args.limit] if args.limit else selected
        with ThreadPoolExecutor(4) as pool:
            for i, _ in enumerate(pool.map(lambda ident: research.enrich(ident, True), targets), 1):
                if i % 20 == 0:
                    print("read", i, "/", len(targets), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
