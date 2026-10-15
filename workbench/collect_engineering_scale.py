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

# Public faculty directories used to widen the engineering corpus. Each entry names
# the parser that understands that school's layout; structures differ enough that a
# per-source parser is required rather than one shared template.
SOURCES: dict[str, dict] = {
    "ustb_metallurgy": {
        "parser": "ustb",
        "code": "0806",
        "institution": "北京科技大学",
        "department": "冶金工程（学科索引）",
        "name": "冶金工程",
        "listing": ("https://faculty.ustb.edu.cn/xkjslb.jsp?totalpage=13&PAGENUM={page}"
                    "&id=5634&lang=zh_CN&st=0"
                    "&urltype=tsites.DisciplineTeacherList&wbtreeid=1014"),
        "max_pages": 14,
    },
    "whu_surveying": {
        "parser": "whu",
        "code": "0816",
        "institution": "武汉大学",
        "department": "测绘学院",
        "name": "测绘科学与技术",
        "listing": "https://www.sgg.whu.edu.cn/szdw/zyjs.htm",
        "max_pages": 1,
    },
}

# The discipline index also lists non-teaching entries. Only clear personnel or
# party/union offices are dropped; research institutes and collaborative centres
# are legitimate research units and are kept.
ADMINISTRATIVE_UNIT = re.compile(r"党委|党支部|办公室|工会|离退休|人事处|财务处|"
                                 r"研究生院|教务处|机关")


def fetch(url: str) -> str:
    response = requests.get(url, headers=UA, timeout=TIMEOUT, verify=False)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_ustb(html: str, url: str, spec: dict) -> list[dict]:
    """Extract teacher cards from one listing page.

    Each card is ``li > a > div.namebox`` holding ``span``（职称）, ``h1``（姓名）
    and the first ``p``（院系）; the two ``i`` counters at the bottom are platform
    view/praise counts and are deliberately not read.
    """
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for anchor in soup.select("a[href]"):
        href = anchor["href"]
        if not re.search(r"faculty\.ustb\.edu\.cn/[A-Za-z0-9_]+/zh_CN/index\.htm$", href):
            continue
        box = anchor.select_one("div.namebox")
        if box is None:
            continue
        title_el = box.select_one("span")
        name_el = box.select_one("h1")
        dept_el = box.select_one("p")
        if name_el is None:
            continue
        name = re.sub(r"\s+", "", name_el.get_text(" ", strip=True))
        if not NAME_RE.fullmatch(name):
            continue
        title = re.sub(r"\s+", "", title_el.get_text(" ", strip=True)) if title_el else ""
        dept = re.sub(r"\s+", "", dept_el.get_text(" ", strip=True)) if dept_el else ""
        # Administrative and party-affairs offices appear in the same index but are
        # not teaching units, so they are not recorded as a mentor's department.
        if ADMINISTRATIVE_UNIT.search(dept):
            continue
        note = (f"学校教师主页按学科索引列出（所在单位：{dept or '未标注'}"
                f"{'，职称：' + title if title else ''}）；索引不含个人研究方向。"
                f"导师资格与招生专业以当年招生公告为准。")
        rows.append(roster_row(
            name, spec["institution"], dept or spec["name"], spec["code"],
            NO_DIRECTION, href, url, "学校教师主页学科索引", note,
        ))
    return rows


def parse_whu(html: str, url: str, spec: dict) -> list[dict]:
    """武汉大学测绘学院: ``p.title04`` gives the 研究所, ``h3`` gives the 职称.

    The page wraps everything in ``div.techer_list``; headings and the
    ``ul.teacher`` blocks appear as siblings in document order, so a single pass
    carries the current institute and rank forward. Names contain full-width
    spaces ("邓　非"), which are removed before validation. Some entries link to a
    placeholder ``#``, so those keep the listing page as their source.
    """
    soup = BeautifulSoup(html, "html.parser")
    for nav in soup.select("ul.am-nav, div.nei_left"):
        nav.decompose()
    root = soup.select_one("div.techer_list") or soup
    rows: list[dict] = []
    institute = ""
    rank = ""
    for node in root.find_all(["p", "h3", "ul"]):
        classes = node.get("class") or []
        if node.name == "p" and "title04" in classes:
            institute = re.sub(r"\s+", "", node.get_text(" ", strip=True))
            continue
        if node.name == "h3":
            rank = re.sub(r"\s+", "", node.get_text(" ", strip=True))
            continue
        if node.name != "ul" or "teacher" not in classes:
            continue
        for li in node.find_all("li"):
            anchor = li.find("a")
            if anchor is None:
                continue
            name = re.sub(r"[\s\u3000]+", "", anchor.get_text(" ", strip=True))
            if not NAME_RE.fullmatch(name):
                continue
            href = (anchor.get("href") or "").strip()
            homepage = href if href.startswith("http") else url
            unit = "·".join(x for x in (institute, rank) if x) or spec["department"]
            note = (f"学院专业教师名录按研究所与职称分组列出（{institute or '未标注所'}，"
                    f"{rank or '职称未标注'}）；名录不含个人研究方向。"
                    f"导师资格与招生专业以当年招生公告为准。")
            rows.append(roster_row(
                name, spec["institution"], unit, spec["code"],
                NO_DIRECTION, homepage, url, "学院专业教师名录", note,
            ))
    return rows


PARSERS = {"ustb": parse_ustb, "whu": parse_whu}


def collect(pages_per_source: int | None = None) -> tuple[list[dict], list[dict], list[dict]]:
    """Read every registered directory and return (rows, pages, failures)."""
    rows: list[dict] = []
    pages: list[dict] = []
    failures: list[dict] = []
    for key, spec in SOURCES.items():
        parser = PARSERS[spec["parser"]]
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
