"""Selection-first catalog and evidence-bounded investigation dossiers.

The old IC corpus is exposed as historical leads, without its evaluative scores.
Other disciplines can enter through sourced pilot records or a user's project.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from . import core
from . import scope

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
PILOT = ROOT / "workbench" / "examples" / "official_source_pilot.json"
OFFICIAL = ROOT / "workbench" / "reference" / "official_faculty.json"
ADMISSION = ROOT / "workbench" / "reference" / "admission_faculty.json"
DISCIPLINES_2022 = ROOT / "workbench" / "reference" / "first_level_disciplines_2022.json"
CASE_STATUSES = {"待核查", "已人工核查", "需补证据", "不适用"}
EVIDENCE_CATEGORIES = {
    "官方身份与任职", "研究方向", "论文与成果", "学术关系",
    "招生与培养", "项目与专利", "其他公开记录",
}
EVIDENCE_STATUSES = {"待人工核查", "已人工核查", "需补证据"}
CASE_SECTIONS = (
    "身份与任职", "研究方向", "论文归属", "论文原文核读",
    "学术关系", "招生与培养", "公开声明对照", "多源交叉核查",
)
# Labels that stand in for "no discipline chosen yet"; they are not disciplines and
# must never appear as navigation options.
UNCLASSIFIED_LABELS = {"学科待归类"}


def stable_id(prefix: str, key: str) -> str:
    return prefix + "-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]


@lru_cache(maxsize=1)
def static_catalog() -> tuple[list[dict], dict, dict, dict]:
    ranked = json.loads((PROCESSED / "mentor_ranked.json").read_text(encoding="utf-8"))
    network = json.loads((PROCESSED / "network_final.json").read_text(encoding="utf-8"))
    curated = json.loads((PROCESSED / "curated.json").read_text(encoding="utf-8"))
    pilot = json.loads(PILOT.read_text(encoding="utf-8"))["profiles"]
    entries: list[dict] = []
    raw: dict[str, dict] = {}
    curated_by_key = {(r["school"], r["name"]): r for r in curated}
    for row in ranked:
        profile = core.normalize_profile(row)
        if profile is None:
            continue
        key = f"{row['school']}|{row['name_cn']}"
        profile["id"] = stable_id("legacy", key)
        profile["origin"] = "历史 IC 专题"
        profile["network_key"] = key
        profile["imported_from"] = "原集成电路导师库"
        # The legacy corpus predates the 2022 discipline catalogue and carried no
        # first-level discipline. Assign it from the curated primary_direction plus
        # research keywords so these rows sit inside the engineering scope instead
        # of a permanent "待核定" bucket.
        assigned = scope.legacy_discipline(
            row.get("research_keywords"), row.get("primary_direction"))
        profile["first_level_discipline"] = assigned
        profile["discipline_assignments"] = [{
            "first_level_discipline": assigned,
            "subject": "",
            "direction": core.clean_text(row.get("primary_direction"), 120) or "方向待补",
            "year": None,
            "degree_level": "",
            "url": "",
            "record_kind": "legacy_keyword_assignment",
            "source_kind": "按研究关键词归入一级学科",
            "classification_basis": "历史专题数据按研究关键词归入工学一级学科导航；"
                                     "不代替该教师所在机构的招生专业认定。",
            "note": "学科归属由公开研究关键词推断，用于工学导航；招生专业以所在机构当年目录为准。",
        }]
        entries.append(profile)
        raw[profile["id"]] = {"ranked": row, "curated": curated_by_key.get((row["school"], row["name_cn"]))}
    for row in pilot:
        profile = core.normalize_profile(row)
        if profile is None:
            continue
        profile["id"] = stable_id("pilot", f"{row['institution']}|{row['name']}")
        profile["origin"] = "公开来源试点"
        profile["imported_from"] = "official_source_pilot.json"
        entries.append(profile)
    expansion = json.loads(OFFICIAL.read_text(encoding="utf-8")) if OFFICIAL.exists() else {"profiles": []}
    existing = {(p['institution'],p['department'],p['name']): p for p in entries}
    for row in expansion["profiles"]:
        profile = core.normalize_profile(row)
        if profile is None:
            continue
        key = (profile['institution'],profile['department'],profile['name'])
        profile["id"] = stable_id("official", f"{profile['institution']}|{profile['department']}|{profile['name']}")
        profile["origin"] = "高校官网名录"
        profile["imported_from"] = "official_faculty.json"
        profile["collected_at"] = row.get("collected_at", "")
        profile["classification_basis"] = row.get("classification_basis", "")
        profile["catalog_source"] = "official_faculty.json"
        if key in existing:
            previous = existing[key]
            # Keep saved investigations and the historical network under their existing ID.
            profile["id"] = previous["id"]
            if previous.get("network_key"):
                profile["origin"] = "高校官网名录 · 历史 IC 资料"
            previous.update(profile)
            continue
        existing[key] = profile
        entries.append(profile)
    admissions = json.loads(ADMISSION.read_text(encoding='utf-8')) if ADMISSION.exists() else {'profiles': []}
    for row in admissions['profiles']:
        key = (row['institution'], row['department'], row['name'])
        previous = existing.get(key)
        if previous:
            previous['discipline_assignments'] = row['discipline_assignments']
            previous['admission_catalog'] = True
            previous.setdefault('collected_at', row['collected_at'])
            for source in row['sources']:
                if source not in previous['sources']:previous['sources'].append(source)
            if not previous.get('homepage'):previous['homepage']=row.get('homepage','')
            continue
        profile = core.normalize_profile(row)
        if not profile:continue
        directory=all(a.get('record_kind')=='faculty_directory' for a in row['discipline_assignments'])
        secondary=all(a.get('evidence_level')=='secondary' for a in row['discipline_assignments'])
        profile.update(id=stable_id('official', '|'.join(key)), origin='转载导师名录 · 待核实' if secondary else ('高校导师名录' if directory else '高校招生目录'),
                       imported_from='admission_faculty.json', catalog_source='admission_faculty.json',
                       secondary_source=secondary,
                       collected_at=row['collected_at'], classification_basis=row['classification_basis'],
                       discipline_assignments=row['discipline_assignments'], admission_catalog=True)
        existing[key]=profile;entries.append(profile)
    return entries, {p["id"]: p for p in entries}, raw, network


def all_entries(project_id: str = "", include_non_engineering: bool = False) -> list[dict]:
    """Catalogue entries, restricted to the engineering scope by default.

    Non-engineering rows stay in the data files and keep their IDs; they are only
    filtered out of the default view. Pass ``include_non_engineering=True`` (the
    interface's "显示非工科" switch) to see everything.
    """
    entries = list(static_catalog()[0])
    if project_id:
        project = core.load_project(project_id)
        for profile in project["profiles"]:
            item = dict(profile)
            item["id"] = f"project-{project_id}-{profile['id']}"
            item["origin"] = f"我的项目：{project['name']}"
            entries.append(item)
    if not include_non_engineering:
        entries = [p for p in entries if in_scope(p)]
    return entries


def in_scope(profile: dict) -> bool:
    """True when the entry belongs to the default engineering scope.

    A user's own additions (``project-`` ids) are always in scope: the engineering
    filter is about which curated corpus is shown, and it must never hide records
    the user created themselves. Entries with no parsable discipline code are also
    kept, so a profile added before a discipline is chosen stays visible.
    """
    if str(profile.get("id", "")).startswith("project-"):
        return True
    names = subject_names(profile)
    codes = {scope.code_of(n) for n in names}
    codes.discard("")
    if not codes:
        return True
    return any(code.startswith(scope.ENGINEERING_PREFIX) for code in codes)


def entry_by_id(mentor_id: str) -> dict | None:
    cached = static_catalog()[1].get(mentor_id)
    if cached:
        return cached
    match = re.fullmatch(r"project-([0-9a-f]{32})-([0-9a-f]{32})", mentor_id)
    if match:
        try:
            project = core.load_project(match.group(1))
        except (ValueError, FileNotFoundError):
            return None
        for profile in project["profiles"]:
            if profile["id"] == match.group(2):
                item = dict(profile)
                item["id"] = mentor_id
                item["origin"] = f"我的项目：{project['name']}"
                return item
    return None


def card(profile: dict) -> dict:
    return {key: profile.get(key, "") for key in (
        "id", "name", "institution", "department", "discipline",
        "first_level_discipline", "direction_group", "interests", "homepage", "origin", "collected_at", "classification_basis",
        "discipline_assignments", "admission_catalog", "secondary_source",
    )} | {"source_count": len(profile.get("sources", []))}


def search_name(query: str, project_id: str = "", limit: int = 40,
                include_non_engineering: bool = False) -> list[dict]:
    query = core.clean_text(query, 80).casefold()
    if not query:
        return []
    matched = [p for p in all_entries(project_id, include_non_engineering)
               if query in p["name"].casefold()]
    matched.sort(key=lambda p: (
        p["name"].casefold() != query,
        not p["name"].casefold().startswith(query),
        p["name"], p["institution"], p["department"],
    ))
    return [card(p) for p in matched[:max(1, min(limit, 100))]]


def subject_names(profile: dict) -> set[str]:
    return {profile.get('first_level_discipline') or '学科待归类'} | {
        row['first_level_discipline'] for row in profile.get('discipline_assignments', [])}


def visible_subject_names(profile: dict, include_non_engineering: bool = False) -> set[str]:
    """Discipline labels to count for this entry under the current scope.

    Kept consistent with :func:`in_scope`: an entry that qualifies as engineering
    through *any* of its assignments contributes only its engineering labels, so a
    cross-listed profile cannot leak a non-engineering discipline into the default
    view. Without this, a mentor listed under both 0801 力学 and 0701 数学 would
    make 数学 appear populated even though the profile was filtered as engineering.
    """
    names = subject_names(profile)
    if include_non_engineering:
        return names
    engineering = {n for n in names if scope.is_engineering(n)}
    return engineering or names


def subject_directions(profile: dict, discipline: str) -> set[str]:
    found={row['direction'] for row in profile.get('discipline_assignments', [])
           if row['first_level_discipline']==discipline}
    return found or {profile.get('direction_group') or '方向待补'}


def disciplines(project_id: str = "", include_non_engineering: bool = False) -> list[dict]:
    """Every catalogue discipline, with the entry count inside the current scope.

    The full 2022 list is always returned so the navigation structure stays
    intact; a non-engineering discipline simply reports count 0 until the caller
    opts in via ``include_non_engineering``.

    Synthetic placeholders (``学科待归类`` for profiles whose discipline is still
    empty, and any other label without a catalogue code) are counted but not
    listed, because they are not first-level disciplines.
    """
    entries = all_entries(project_id, include_non_engineering)
    counts = Counter(name for p in entries
                     for name in visible_subject_names(p, include_non_engineering))
    official = json.loads(DISCIPLINES_2022.read_text(encoding="utf-8"))["disciplines"]
    names = [f"{item['code']} {item['name']}" for item in official]
    known = set(names)
    extra = sorted(n for n in set(counts) - known
                   if scope.code_of(n) and n not in UNCLASSIFIED_LABELS)
    return [{"name": name, "count": counts[name], "engineering": scope.is_engineering(name)}
            for name in names + extra]


def scope_info() -> dict:
    """Scope metadata for the interface's engineering / non-engineering switch."""
    entries = static_catalog()[0]
    engineering = sum(1 for p in entries if in_scope(p))
    return {
        **scope.scope_summary(),
        "engineering_records": engineering,
        "non_engineering_records": len(entries) - engineering,
        "total_records": len(entries),
        "default_view": "engineering",
        "switch_label": "显示非工科",
    }


def public_counts() -> dict:
    """公开来源的**轻量计数**：不读逐人档案，给首页首屏用。

    ``coverage()`` 需要对 1.2 万条记录逐条取档案来统计论文/关系/招生，
    冷启动要 8–17 秒；首页只显示「多少条、多少所、多少学科」时没必要付这个代价。
    """
    entries = static_catalog()[0]
    public = [p for p in entries
              if p.get("catalog_source") or (p.get("id") or "").startswith("pilot-")]
    official = [p for p in public if not p.get("secondary_source")]
    institutions = {p.get("institution") for p in public if p.get("institution")}
    names = {p.get("first_level_discipline") for p in public if p.get("first_level_discipline")}
    engineering = {n for n in names if (n or "")[:2] == "08"}
    info = scope_info()
    return {
        "total_records": len(entries),
        "public_records": len(public),
        "official_records": len(official),
        "secondary_records": len(public) - len(official),
        "public_institutions": len(institutions),
        "disciplines_total": len(names),
        "disciplines_engineering": len(engineering),
        "engineering_records": info.get("engineering_records"),
        "non_engineering_records": info.get("non_engineering_records"),
    }


def coverage() -> dict:
    from . import public_research
    entries = static_catalog()[0]
    public = [p for p in entries if p.get('catalog_source') or p['id'].startswith('pilot-')]
    official = [p for p in public if not p.get('secondary_source')]
    counts = Counter(name for p in public for name in subject_names(p))
    reports = [data for p in public if (data := public_research.load(p['id'])) and data['status'] in {'ready','catalog'}]
    return {"total_records": len(entries), "official_records": len(official),
            "public_records": len(public), "secondary_records": len(public)-len(official),
            "public_institutions": len({p['institution'] for p in public}),
            "official_disciplines": len({name for p in official for name in subject_names(p)}),
            "legacy_records": sum(p['id'].startswith('legacy-') for p in entries),
            "overlapping_records": sum(p['id'].startswith('legacy-') for p in official),
            "research": {"readable_profiles": len(reports),
                         **{key: sum(bool(data.get(key)) for data in reports)
                            for key in ('papers','relations','recruitment','admission_notices')}},
            "official_institutions": len({p['institution'] for p in official}),
            "updated_at": max((p.get('collected_at','') for p in official), default=''),
            "disciplines": [{"name":name,"count":count,"institutions":len({p['institution'] for p in public if name in subject_names(p)}),
                             "secondary_count":sum(bool(p.get('secondary_source')) for p in public if name in subject_names(p))}
                            for name,count in sorted(counts.items())]}


def institutions(discipline: str, project_id: str = "",
                 include_non_engineering: bool = False) -> list[dict]:
    counts = Counter(p["institution"] for p in all_entries(project_id, include_non_engineering)
                     if discipline in subject_names(p))
    return [{"name": key, "count": count} for key, count in sorted(counts.items())]


def directions(discipline: str, institution: str, project_id: str = "",
               include_non_engineering: bool = False) -> list[dict]:
    counts = Counter(direction for p in all_entries(project_id, include_non_engineering)
                     if discipline in subject_names(p) and (institution=='__all__' or p['institution']==institution)
                     for direction in subject_directions(p, discipline))
    return [{"name": key, "count": count} for key, count in sorted(counts.items())]


def mentors(discipline: str, institution: str, direction: str, project_id: str = "",
            include_non_engineering: bool = False) -> list[dict]:
    found = [p for p in all_entries(project_id, include_non_engineering)
             if discipline in subject_names(p) and (institution=='__all__' or p["institution"] == institution)
             and (direction == "__all__" or direction in subject_directions(p, discipline))]
    return [card(p) | {'first_level_discipline':discipline,
                      'direction_group':direction if direction!='__all__' else '；'.join(sorted(subject_directions(p,discipline)))}
            for p in sorted(found, key=lambda p: (p["name"], p["department"]))]


@lru_cache(maxsize=1)
def network_index() -> dict[str, dict[str, list[dict]]]:
    network = static_catalog()[3]
    index: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    by_short_key = {}
    for person_id, item in static_catalog()[2].items():
        row = item["ranked"]
        by_short_key[(row.get("school_key"), row.get("name_cn"))] = static_catalog()[1][person_id]["network_key"]
    for kind in ("advisor", "overlap", "collab", "sibling"):
        for edge in network.get(kind, []):
            for key in {edge.get("s"), edge.get("t")} - {None}:
                index[key][kind].append(edge)
    for edge in network.get("external", []):
        short_school, _, name = str(edge.get("stu", "")).partition("|")
        key = by_short_key.get((short_school, name))
        if key:
            index[key]["external"].append(edge)
    return index


def _relations(profile: dict) -> dict:
    key = profile.get("network_key")
    if not key:
        return {"advisor": [], "overlap": [], "collab": [], "sibling": [], "external": [],
                "message": "当前资料没有可关联的既有关系网；不等于不存在学术关系。"}
    network = static_catalog()[3]
    related = network_index().get(key, {})
    def person(other: str) -> str:
        node = network.get("nodes", {}).get(other, {})
        return f"{node.get('name', other.split('|')[-1])} · {node.get('school', '')}"
    result: dict[str, list[dict] | str] = {}
    for kind in ("advisor", "overlap", "collab", "sibling"):
        values = []
        for edge in related.get(kind, [])[:50]:
            other = edge.get("t") if edge.get("s") == key else edge.get("s")
            values.append({
                "person": person(other or ""), "level": edge.get("lv"),
                "direction": "本人为学生" if edge.get("s") == key else "本人为导师",
                "basis": core.clean_text(edge.get("basis") or edge.get("type") or "", 100),
                "note": core.clean_text(edge.get("note"), 320),
                "papers": edge.get("n"), "span": core.clean_text(edge.get("span"), 60),
            })
        result[kind] = values
    result["external"] = [{
        "person": core.clean_text(edge.get("mentor"), 120),
        "level": "外部记录", "direction": "外部师承候选",
        "basis": core.clean_text(edge.get("kind"), 80),
        "note": "历史专题保留的外部姓名线索；此条未附原始证据，须另查本人页面或可靠来源。",
        "papers": None, "span": "",
    } for edge in related.get("external", [])[:30]]
    result["message"] = "关系网为 2026-10-12 的 IC 专题产物；L1 自述、L2 交叉、L3 署名推断、L4 共同署名应分开看。"
    return result


def dossier(mentor_id: str) -> dict | None:
    from . import public_research
    from .investigation import archive_for
    profile = entry_by_id(mentor_id)
    if profile is None:
        return None
    resolved = public_research.registered_source(profile)
    if resolved.get("homepage"):
        profile = {**profile, "homepage": resolved["homepage"]}
    raw = static_catalog()[2].get(mentor_id)
    papers = []
    production = None
    recruit = None
    if raw:
        ranked = raw["ranked"]
        production = {
            "candidate_papers": ranked.get("n_ic_papers", 0),
            "attribution_confidence": ranked.get("confidence"),
            "ambiguity": ranked.get("ambiguity"),
            "recall_risk": ranked.get("recall_risk"),
            "caveat": "历史 IC 专题的候选匹配数量；同名和论文归属尚需逐篇核查，不是成果质量评分。",
        }
        candidates = sorted(ranked.get("papers", []), key=lambda p: (-(p.get("year") or 0), p.get("title") or ""))
        for paper in candidates[:12]:
            doi = str(paper.get("doi") or "").strip()
            papers.append({
                "title": core.clean_text(paper.get("title"), 350),
                "year": paper.get("year"), "venue": core.clean_text(paper.get("venue"), 180),
                "doi": doi, "url": f"https://doi.org/{quote(doi, safe='/')}" if doi else "",
            })
        curated = raw.get("curated")
        if curated:
            recruit = {"historical_signal_count": curated.get("recruit_signal_count", 0),
                       "caveat": "旧页曾抽取到的招生表述线索；不代表当前招生，须打开官方页面重新确认。"}
    return {
        "profile": card(profile), "sources": profile.get("sources", []),
        # Identity key for the relationship network and the student reference score.
        # Kept out of card() so list views stay compact.
        "network_key": profile.get("network_key", ""),
        "public_research": public_research.load(mentor_id),
        "previous_research": archive_for(profile),
        "origin": profile.get("origin", ""), "production": production,
        "papers": papers, "recruitment": recruit, "relations": _relations(profile),
        "sections": CASE_SECTIONS, "case": load_case(mentor_id),
    }


def _case_path(mentor_id: str) -> Path:
    name = hashlib.sha256(mentor_id.encode("utf-8")).hexdigest()
    return core.DATA_DIR / "investigations" / f"{name}.json"


def load_case(mentor_id: str) -> dict:
    path = _case_path(mentor_id)
    if path.exists():
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
            if stored.get("mentor_id") == mentor_id:
                for section in CASE_SECTIONS:
                    stored.setdefault("section_status", {}).setdefault(section, "待核查")
                stored.setdefault("openalex_author_id", "")
                stored.setdefault("openalex_snapshot", None)
                stored.setdefault("evidence", [])
                stored.setdefault("manual_papers", [])
                return stored
        except (OSError, ValueError):
            pass
    return {"mentor_id": mentor_id, "section_status": {key: "待核查" for key in CASE_SECTIONS},
            "notes": "", "evidence": [], "manual_papers": [], "openalex_author_id": "", "openalex_snapshot": None,
            "updated_at": None}


def _write_case(record: dict) -> None:
    path = _case_path(record["mentor_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def update_case(mentor_id: str, changes: dict) -> dict:
    if entry_by_id(mentor_id) is None:
        raise ValueError("找不到这位导师")
    record = load_case(mentor_id)
    for section, status in changes.get("section_status", {}).items():
        if section not in CASE_SECTIONS or status not in CASE_STATUSES:
            raise ValueError("无效的调查项或状态")
        record["section_status"][section] = status
    if "notes" in changes:
        record["notes"] = core.clean_text(changes["notes"], 3000)
    if "openalex_author_id" in changes:
        from .openalex import AUTHOR_ID
        author_id = str(changes["openalex_author_id"])
        if not AUTHOR_ID.fullmatch(author_id):
            raise ValueError("无效的 OpenAlex 作者 ID")
        if record.get("openalex_author_id") != author_id:
            record["openalex_snapshot"] = None
        record["openalex_author_id"] = author_id
    record["updated_at"] = core.now()
    _write_case(record)
    return record


def add_evidence(mentor_id: str, data: dict) -> dict:
    if entry_by_id(mentor_id) is None:
        raise ValueError("找不到这位导师")
    category = core.clean_text(data.get("category"), 40)
    title = core.clean_text(data.get("title"), 160)
    url = core.safe_url(data.get("url"))
    claim = core.clean_text(data.get("claim"), 500)
    if category not in EVIDENCE_CATEGORIES or not title or not url:
        raise ValueError("请选择证据类别，并填写短标题和有效的 http(s) 来源链接")
    record = load_case(mentor_id)
    if len(record["evidence"]) >= 200:
        raise ValueError("单人最多保存 200 条证据")
    item = {"id": uuid.uuid4().hex, "category": category, "title": title,
            "url": url, "claim": claim, "status": "待人工核查", "added_at": core.now()}
    record["evidence"].append(item)
    record["updated_at"] = core.now()
    _write_case(record)
    return record


def update_evidence(mentor_id: str, evidence_id: str, status: str) -> dict:
    if entry_by_id(mentor_id) is None:
        raise ValueError("找不到这位导师")
    if status not in EVIDENCE_STATUSES:
        raise ValueError("无效的证据状态")
    record = load_case(mentor_id)
    item = next((entry for entry in record["evidence"] if entry["id"] == evidence_id), None)
    if item is None:
        raise ValueError("找不到这条证据")
    item["status"] = status
    item["checked_at"] = core.now() if status == "已人工核查" else None
    record["updated_at"] = core.now()
    _write_case(record)
    return record


def remove_evidence(mentor_id: str, evidence_id: str) -> dict:
    if entry_by_id(mentor_id) is None:
        raise ValueError("找不到这位导师")
    record = load_case(mentor_id)
    remaining = [entry for entry in record["evidence"] if entry["id"] != evidence_id]
    if len(remaining) == len(record["evidence"]):
        raise ValueError("找不到这条证据")
    record["evidence"] = remaining
    record["updated_at"] = core.now()
    _write_case(record)
    return record


def refresh_openalex(mentor_id: str) -> dict:
    if entry_by_id(mentor_id) is None:
        raise ValueError("找不到这位导师")
    record = load_case(mentor_id)
    if not record.get("openalex_author_id"):
        raise ValueError("请先选择正确的 OpenAlex 作者记录")
    from .openalex import works_snapshot
    author_id = record["openalex_author_id"]
    snapshot = works_snapshot(author_id)
    record = load_case(mentor_id)
    if record.get("openalex_author_id") != author_id:
        raise ValueError("已更换作者，请重新读取论文")
    record["openalex_snapshot"] = snapshot
    record["openalex_snapshot"]["fetched_at"] = core.now()
    record["updated_at"] = core.now()
    _write_case(record)
    return record


def add_paper(mentor_id: str, data: dict) -> dict:
    from .investigation import normalize_doi
    if entry_by_id(mentor_id) is None:
        raise ValueError("找不到这位导师")
    title = core.clean_text(data.get("title"), 350)
    doi = normalize_doi(data.get("doi"))
    url = core.safe_url(data.get("url"))
    year = str(data.get("year") or "").strip()
    if not title or not (doi or url):
        raise ValueError("请填写论文标题，以及 DOI 或论文链接")
    if data.get("doi") and not doi:
        raise ValueError("DOI 格式不对，可填写 10. 开头的编号或 doi.org 链接")
    if year and (not year.isdigit() or not 1800 <= int(year) <= 2100):
        raise ValueError("请填写四位发表年份")
    record = load_case(mentor_id)
    if len(record["manual_papers"]) >= 100:
        raise ValueError("每位导师最多补充 100 篇论文")
    if any((doi and item.get("doi") == doi) or (not doi and item.get("url") == url and item["title"] == title)
           for item in record["manual_papers"]):
        raise ValueError("这篇论文已经添加过了")
    record["manual_papers"].append({"id": uuid.uuid4().hex, "title": title, "doi": doi,
        "year": int(year) if year else None, "url": url or "https://doi.org/" + quote(doi, safe="/"),
        "venue": "", "added_at": core.now(), "status": "待人工核查"})
    record["updated_at"] = core.now()
    _write_case(record)
    return record


def remove_paper(mentor_id: str, paper_id: str) -> dict:
    if entry_by_id(mentor_id) is None:
        raise ValueError("找不到这位导师")
    record = load_case(mentor_id)
    remaining = [item for item in record["manual_papers"] if item["id"] != paper_id]
    if len(remaining) == len(record["manual_papers"]):
        raise ValueError("找不到这篇手动添加的论文")
    record["manual_papers"] = remaining
    record["updated_at"] = core.now()
    _write_case(record)
    return record


def report_markdown(mentor_id: str) -> str:
    data = dossier(mentor_id)
    if data is None:
        raise ValueError("找不到这位导师")
    p = data["profile"]
    lines = [f"# {p['name']}导师调查记录", "", f"- 机构：{p['institution']}",
             f"- 院系：{p['department'] or '未知'}", f"- 一级学科/资料领域：{p['first_level_discipline'] or '未知'}",
             f"- 方向：{p['direction_group'] or '未知'}", f"- 资料来源：{p['origin']}",
             f"- 研究关键词：{p['interests'] or '未收录'}",
             "- 说明：公开资料线索与人工记录，不是对个人的评价或招生结论。", "", "## 来源", ""]
    if data["sources"]:
        for source in data["sources"]:
            lines.append(f"- {source.get('title') or '来源'}：{source['url']}（{source.get('status', '待人工核查')}）")
    else:
        lines.append("- 暂无已登记来源；旧专题主页链接须重新打开核实。")
    if p.get("homepage") and not data["sources"]:
        lines.append(f"- 原记录主页：{p['homepage']}")
    research = data.get("public_research")
    if research:
        lines += ["", "## 公开来源调查资料", "", f"- 整理时间：{research['checked_at']}",
                  "- 学校、个人学术网站及其他已核对来源；年度名录和院系公告不代表个人剩余名额。"]
        for key, label in (("papers", "论文与论著"), ("relations", "师承记录"),
                           ("biography", "教育与任职记录"), ("recruitment", "招生说明与年度名录"),
                           ("admission_notices", "院系招生公告")):
            lines += ["", f"### {label}", ""]
            for row in research.get(key, []):
                metadata = [row.get('source_kind', '公开来源')]
                if row.get('publication_type'):
                    metadata.append(row['publication_type'])
                if row.get('year'):
                    metadata.append(f"{row['year']} 年")
                elif key == 'recruitment':
                    metadata.append('未注明招生年份')
                if key == 'admission_notices':
                    metadata.append('院系公告，不代表个人名额')
                if row.get('fetched_at'):
                    metadata.append(f"读取于 {row['fetched_at']}")
                lines.append(f"- {row['text']}；{'；'.join(metadata)}；来源：{row['url']}")
                if row.get('identity_url'):
                    lines.append(f"  身份核对出处：{row['identity_url']}")
                if row.get('work_url'):
                    lines.append(f"  论文链接：{row['work_url']}")
            if not research.get(key):
                lines.append("- 此次读取未提取到相关内容，请查看原网页。")
        for page in research.get('pages', []):
            lines.append(f"- 已读取：{page['url']}；读取时间：{page['fetched_at']}")
    lines += ["", "## 调查期间补充的来源", ""]
    for item in data["case"]["evidence"]:
        lines.append(f"- [{item['category']}] {item['title']}：{item['url']}；状态：{item['status']}；记录：{item['claim'] or '未填写'}")
    if not data["case"]["evidence"]:
        lines.append("- 尚未补充来源。")
    lines += ["", "## 论文线索", ""]
    if data["production"]:
        lines.append(data["production"]["caveat"])
    for paper in data["papers"]:
        lines.append(f"- {paper['year'] or '年份未知'} {paper['title']} {paper['url']}")
    if not data["papers"]:
        lines.append("- 当前没有经本工作台核实的论文记录。")
    snapshot = data["case"].get("openalex_snapshot")
    if data["case"].get("manual_papers"):
        lines += ["", "### 手动添加的论文（作者归属待核对）", ""]
        for paper in data["case"]["manual_papers"]:
            lines.append(f"- {paper['year'] or '年份未填'} {paper['title']} {paper['url']}")
    if snapshot:
        lines += ["", "### OpenAlex 作者记录（用户选择，仍需逐篇核对）", "",
                  f"- 作者 ID：{snapshot['author_id']}",
                  f"- 抓取时间：{snapshot['fetched_at']}",
                  f"- 范围：{snapshot['caveat']}"]
        for paper in snapshot["papers"]:
            lines.append(f"- {paper['year'] or '年份未知'} {paper['title']} {paper['url']}")
        lines += ["", "### OpenAlex 共同作者（最近作品样本，非师承证明）", ""]
        for author in snapshot.get("coauthors", []):
            lines.append(f"- {author['name']}：样本中 {author['shared_in_sample']} 条共同作品；{author['url']}")
        if not snapshot.get("coauthors"):
            lines.append("- 当前样本未形成可展示的共同作者线索。")
    lines += ["", "## 关系网线索", "", data["relations"]["message"]]
    for kind, label in (("advisor", "师承候选"), ("overlap", "经历重叠"),
                        ("collab", "共同署名"), ("sibling", "同门派生线索"),
                        ("external", "外部师承候选")):
        values = data["relations"][kind]
        lines.append(f"### {label}（展示 {len(values)} 条）")
        for item in values[:20]:
            lines.append(f"- {item['person']}；等级 {item['level']}；{item['note'] or item['basis'] or '详见来源数据'}")
    lines += ["", "## 人工核查进度", ""]
    for section, status in data["case"]["section_status"].items():
        lines.append(f"- {section}：{status}")
    from .investigation import review_guide
    guide = review_guide(data)
    lines += ["", "## 后续核查清单", "", "以下按人工核查状态列出待办，不代表系统已认证资料。"]
    for item in guide["items"]:
        if item["status"] in {"待核查", "需补证据"}:
            lines.append(f"- {item['section']}（{item['status']}）：{item['instruction']} {item['available']}。")
    if not guide["pending"]:
        lines.append("- 当前无待办核查项；仍需按来源时效定期复核。")
    run = data["case"].get("investigation_run")
    if run:
        from .investigation import fingerprint
        lines += ["", "## 最近一次调查任务", "", f"- 整理时间：{run['created_at']}",
                  f"- 说明：{run['caveat']}"]
        if run.get("fingerprint") != fingerprint(data):
            lines.append("- 资料已经变化，此次调查结果需重新整理。")
        for module in run["modules"]:
            lines += ["", f"### {module['label']} · {module['status']}", "", module["summary"]]
            details = module["details"]
            for check in details.get("checks", []):
                lines.append(f"- {check['doi']}：{check['message']}；查询时间 {check['checked_at']}；{check['api_url']}")
                if check.get("title"):
                    lines.append(f"  登记标题：{check['title']}；作者：{'、'.join(check.get('authors', []))}")
            if module["id"] == "archive" and details:
                lines.append(f"- 旧调查日期：{details['date']}")
                for source in details.get("source_urls", []):
                    lines.append(f"- 原档案登记来源：{source}")
                for section in details.get("sections", []):
                    lines += ["", f"#### 历史摘录：{section['title']}", "", section["text"]]
    lines += ["", "## 备注", "", data["case"]["notes"] or "暂无备注", ""]
    return "\n".join(lines)
