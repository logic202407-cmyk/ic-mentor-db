"""Deepen the thinnest disciplines (民族学 / 矿业工程) with sourced faculty rows.

Both target disciplines currently have 8 people from a single institution each:

* 0304 民族学      — 中国社会科学院大学（社会与民族学院）
* 0819 矿业工程    — 江西理工大学（矿业工程学院）

This module adds verifiable faculty from additional public department
directories, following the same contract as ``collect_sparse_disciplines``:
rows carry the exact directory URL they came from, the merge never overwrites an
existing ``(institution, department, name)`` identity, and an audit file records
the before/after counts.

Run ``--dry-run`` first: it parses the directories and prints what would be added
without writing any file or touching the shared catalogue.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from html import escape
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from . import catalog
from . import public_research as research
from .collect_discipline_catalog import CODES, OUT, REFERENCE, aggregate

COLLECTED_AT = "2026-10-15"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120 Safari/537.36"
}
TIMEOUT = (10, 30)
NAME_RE = re.compile(r"^[\u4e00-\u9fff·]{2,8}$")

# Public department directories used as sources. Each entry:
#   key, url, institution, department, discipline code, kind
DIRECTORIES = {    "cumt_mining": {
        "url": "https://cese.cumt.edu.cn/szdw/xyjs.htm",
        "institution": "中国矿业大学",
        "department": "矿业工程学院",
        "code": "0819",
        "kind": "学院在职教师名录",
        "note": "学院在职教师名录，按职称分组；导师资格与招生专业以当年招生公告为准。",
    },
    "muc_ethnology": {
        "url": "https://msy.muc.edu.cn/sz/zrjs/axx/mzxx1.htm",
        "institution": "中央民族大学",
        "department": "民族学与社会学学院·民族学系",
        "code": "0304",
        "kind": "学院在职教师名录",
        "note": "学院按学系公布的专任教师名录；导师资格与招生专业以当年招生公告为准。",
    },
}

# Titles recognised in the CUMT grouping headings and the MUC per-card labels.
TITLE_WORDS = ("教授", "副教授", "讲师", "助理教授", "研究员", "副研究员", "助教", "院士")
# Strings that are navigation chrome rather than a person or a title.
NAV_NOISE = re.compile(
    r"^(首页|上页|下页|尾页|末页|按姓名|按学系|登录|更多|学院概况|学院简介|历任领导|"
    r"现任领导|机构设置|系所链接|学科建设|师资队伍|学院教师|教师名录|教授|副教授|讲师|"
    r"共\d+条|\d+)$"
)


def fetch(url: str) -> tuple[str, str]:
    """Return (final_url, html) for a public page."""
    response = requests.get(url, headers=UA, timeout=TIMEOUT)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.url, response.text


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def clean_direction(value: str) -> str:
    text = BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)
    text = re.split(r"欢迎|承担国家|（学术网页|邮箱|电话", text, maxsplit=1)[0]
    text = re.sub(r"\s+", " ", text).strip(' “”。;；,，')
    return text or "方向待补"


def roster_row(name, school, department, code, direction, homepage, source, kind, note):
    if not NAME_RE.fullmatch(name):
        raise ValueError("Unexpected name: " + repr(name))
    return {
        "name": name,
        "institution": school,
        "department": department,
        "homepage": homepage,
        "collected_at": COLLECTED_AT,
        "assignment": {
            "first_level_discipline": CODES[code],
            "subject": code + "00 " + CODES[code][5:],
            "direction": clean_direction(direction),
            "year": None,
            "degree_level": "",
            "url": source,
            "record_kind": "faculty_directory",
            "source_kind": kind,
            "classification_basis": "按公开院系名录与研究领域归入学科导航；不代替招生专业认定",
            "note": note,
        },
    }


# Directory pages list teachers grouped by 职称, not by research area. The rank
# label must never be presented as a research direction, so it is kept in the
# note and the direction is left explicitly unknown.
NO_DIRECTION = "方向待补"

# The disciplines this batch deepens. "added" is reported over these targets only,
# computed from the preserved baseline, so a later re-run cannot reset it to zero.
TARGET_DISCIPLINES = ("0304 民族学", "0819 矿业工程")


def parse_cumt(html: str, url: str, spec: dict) -> list[dict]:
    """中国矿业大学矿业工程学院: div.item groups teachers under a 职称 heading."""
    soup = BeautifulSoup(html, "html.parser")
    rows, seen = [], set()
    for item in soup.select("div.item"):
        heading = norm(item.get_text(" ", strip=True))
        title = next((t for t in TITLE_WORDS if heading.startswith(t)), "")
        if not title:
            continue
        holder = item.select_one("div.list_avatar") or item
        for a in holder.select("a[href]"):
            name = norm(a.get_text(" ", strip=True))
            if not NAME_RE.fullmatch(name) or name in seen:
                continue
            seen.add(name)
            note = (f"学院在职教师名录按职称分组列出（本条目所在分组：{title}）；"
                    f"名录未列个人研究方向。导师资格与招生专业以当年招生公告为准。")
            rows.append(roster_row(
                name, spec["institution"], spec["department"], spec["code"],
                NO_DIRECTION, urljoin(url, a["href"]), url, spec["kind"], note,
            ))
    return rows


def parse_muc(html: str, url: str, spec: dict) -> tuple[list[dict], list[str], int]:
    """中央民族大学民族学与社会学学院: ul.list_box_n_xyld, 3 per page + pagination."""
    soup = BeautifulSoup(html, "html.parser")
    rows, seen = [], set()
    for a in soup.select("ul.list_box_n_xyld a[href]"):
        if "/info/" not in a["href"]:
            continue
        parts = [norm(x) for x in a.get_text(" ", strip=True).split() if norm(x)]
        if not parts:
            continue
        name = parts[0]
        if not NAME_RE.fullmatch(name) or name in seen:
            continue
        seen.add(name)
        rank = next((p for p in parts[1:] if any(t in p for t in TITLE_WORDS)), "")
        note = (f"学院按学系公布的专任教师名录列出（{spec['department'].split('·')[-1]}"
                f"{'，职称：' + rank if rank else ''}）；名录未列个人研究方向。"
                f"导师资格与招生专业以当年招生公告为准。")
        rows.append(roster_row(
            name, spec["institution"], spec["department"], spec["code"],
            NO_DIRECTION, urljoin(url, a["href"]), url, spec["kind"], note,
        ))
    # pagination: sibling links of the form N.htm
    pages, total = set(), 0
    for a in soup.select("a[href]"):
        href = a["href"]
        if re.fullmatch(r"\d+\.htm", href) and "/info/" not in href:
            pages.add(urljoin(url, href))
    m = re.search(r"共\s*(\d+)\s*条", soup.get_text(" ", strip=True))
    if m:
        total = int(m.group(1))
    return rows, sorted(pages), total


def collect() -> tuple[list[dict], list[dict], list[dict]]:
    rows: list[dict] = []
    pages: list[dict] = []
    failures: list[dict] = []

    for key, spec in DIRECTORIES.items():
        try:
            final, html = fetch(spec["url"])
        except Exception as exc:  # noqa: BLE001
            failures.append({"key": key, "url": spec["url"],
                             "error": f"{type(exc).__name__}: {exc}"})
            continue
        pages.append({"url": final, "collected_at": COLLECTED_AT})

        if key == "cumt_mining":
            rows.extend(parse_cumt(html, final, spec))
        else:
            first, page_urls, total = parse_muc(html, final, spec)
            rows.extend(first)
            # Follow the department's own pagination on the same host only.
            for pu in page_urls:
                if not pu.startswith(spec["url"].rsplit("/", 1)[0]):
                    continue
                try:
                    pf, ph = fetch(pu)
                except Exception as exc:  # noqa: BLE001
                    failures.append({"key": key, "url": pu,
                                     "error": f"{type(exc).__name__}: {exc}"})
                    continue
                pages.append({"url": pf, "collected_at": COLLECTED_AT})
                more, _, _ = parse_muc(ph, pf, spec)
                rows.extend(more)

    # De-duplicate within this batch, keeping the first (most specific) source page.
    unique: dict[tuple, dict] = {}
    for row in rows:
        unique.setdefault((row["institution"], row["department"], row["name"]), row)
    return list(unique.values()), pages, failures


def merge(supplement: dict, dry_run: bool) -> dict:
    """Merge into the discipline catalogue without replacing existing identities."""
    current = json.loads(OUT.read_text(encoding="utf8"))
    by_key = {(p["institution"], p["department"], p["name"]): p for p in current["profiles"]}
    added, enriched = 0, 0
    for p in supplement["profiles"]:
        key = (p["institution"], p["department"], p["name"])
        if key not in by_key:
            if not dry_run:
                current["profiles"].append(p)
            by_key[key] = p
            added += 1
        else:
            target = by_key[key]
            changed = False
            for field in ("discipline_assignments", "sources"):
                for item in p.get(field, []):
                    if item not in target.get(field, []):
                        if not dry_run:
                            target.setdefault(field, []).append(item)
                        changed = True
            if not target.get("homepage") and p.get("homepage") and not dry_run:
                target["homepage"] = p["homepage"]
            if changed:
                enriched += 1
    if not dry_run:
        for page in supplement["pages"]:
            if not any(p["url"] == page["url"] for p in current.get("pages", [])):
                current.setdefault("pages", []).append(page)
        OUT.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    return {"added": added, "enriched": enriched, "total_before": len(by_key) - added}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="parse and report only; write nothing")
    parser.add_argument("--enrich", action="store_true",
                        help="after merging, read each new person's public page")
    parser.add_argument("--limit", type=int, default=0,
                        help="cap how many new profiles to read when --enrich is set")
    args = parser.parse_args()

    rows, pages, failures = collect()
    supplement = {
        "description": "民族学与矿业工程薄弱学科补充（中央民族大学、中国矿业大学）",
        "collected_at": COLLECTED_AT,
        "profiles": aggregate(rows),
        "pages": pages,
        "failures": failures,
    }
    for p in supplement["profiles"]:
        if all(a.get("record_kind") == "faculty_directory" for a in p["discipline_assignments"]):
            p["classification_basis"] = "按公开院系名录和研究领域归入学科导航；不代替招生专业认定"

    if args.dry_run:
        by_disc = {}
        by_dept = {}
        for p in supplement["profiles"]:
            for a in p["discipline_assignments"]:
                by_disc[a["first_level_discipline"]] = by_disc.get(a["first_level_discipline"], 0) + 1
            by_dept[p["department"]] = by_dept.get(p["department"], 0) + 1
        print(json.dumps({
            "profiles": len(supplement["profiles"]),
            "pages": len(pages),
            "failures": failures,
            "by_discipline": by_disc,
            "by_department": by_dept,
        }, ensure_ascii=False, indent=2))
        return 0

    (REFERENCE / "thin_discipline_faculty.json").write_text(
        json.dumps(supplement, ensure_ascii=False, indent=2) + "\n", encoding="utf8")

    # Keep the first observed "before" so a later --enrich re-run (which merges
    # nothing new) cannot overwrite the recorded before/after of this batch.
    audit_path = REFERENCE / "thin_discipline_audit_20261015.json"
    previous = {}
    if audit_path.exists():
        try:
            previous = json.loads(audit_path.read_text(encoding="utf8"))
        except (OSError, ValueError):
            previous = {}
    before = previous.get("before") or {x["name"]: x["count"] for x in catalog.disciplines()}
    outcome = merge(supplement, dry_run=False)
    catalog.static_catalog.cache_clear()
    after = {x["name"]: x["count"] for x in catalog.disciplines()}

    # Register identity sources so public_research can read each new person's page.
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
            reg.update(homepage=row["homepage"],
                       identity_url=row["sources"][0]["url"],
                       source_kind="学院教师主页")
        registry[match["id"]] = reg
    research.SOURCE_REGISTRY.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf8")

    audit = {
        "date": COLLECTED_AT,
        "scope": "民族学（中央民族大学）、矿业工程（中国矿业大学）薄弱学科补充",
        "before": before,
        "after": after,
        "profiles": len(supplement["profiles"]),
        "profile_ids": selected,
        "merge": outcome,
        "pages": [p["url"] for p in pages],
        "failures": failures,
        "limits": [
            "学院在职教师名录用于学科导航归类，不代表当年招生专业或名额。",
            "名录按职称或学系分组，不含个人研究方向，故方向字段一律为“方向待补”；职称只写入来源说明，不作为研究方向。",
            "不收录邮箱、电话等联系方式。",
        ],
    }
    if previous.get("first_recorded_at"):
        audit["first_recorded_at"] = previous["first_recorded_at"]
    else:
        audit["first_recorded_at"] = COLLECTED_AT
    # Net new people over this batch's target disciplines, measured against the
    # preserved baseline rather than against whatever this particular run merged.
    audit["merge"] = dict(outcome)
    audit["merge"]["added"] = sum(
        max(0, after.get(d, 0) - before.get(d, 0)) for d in TARGET_DISCIPLINES)
    audit["merge"]["note"] = "added 为两个目标学科的净新增人数；不含其他学科变动。"
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf8")

    changed = {k: [before.get(k, 0), v] for k, v in after.items() if v != before.get(k, 0)}
    print(json.dumps({"profiles": len(supplement["profiles"]), "merge": outcome,
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
