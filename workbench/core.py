"""Local project storage and source-preserving import for the mentor workbench."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("MENTOR_WORKBENCH_DATA", ROOT / ".workbench-data"))
PROJECTS_DIR = DATA_DIR / "projects"
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PROJECT_ID = re.compile(r"^[0-9a-f]{32}$")
MAX_IMPORT_ROWS = 5000
LEGACY_DIRECTIONS = {
    "device": "电子器件与工艺", "photonics": "光电子与硅光", "rf": "射频与通信",
    "digital_ai": "数字电路与 AI 芯片", "mems": "微机电系统", "analog": "模拟电路",
    "eda": "电子设计自动化", "quantum": "量子技术", "power": "电力电子",
    "other": "集成电路相关",
}

ALIASES = {
    "name": ("name", "姓名", "导师", "教师", "name_cn"),
    "institution": ("institution", "school", "学校", "单位", "机构", "任职单位"),
    "department": ("department", "学院", "院系", "部门"),
    "discipline": ("discipline", "专业", "学科", "领域", "primary_direction"),
    "first_level_discipline": ("first_level_discipline", "一级学科"),
    "direction_group": ("direction_group", "方向分类", "研究方向分类"),
    "interests": ("interests", "research_interests", "research_keywords", "研究方向", "方向", "关键词"),
    "summary": ("summary", "简介", "研究简介", "描述"),
    "homepage": ("homepage", "source_url", "主页", "官网", "链接", "来源链接"),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_text(value: object, limit: int = 500) -> str:
    if isinstance(value, list):
        value = "、".join(str(item) for item in value)
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    return EMAIL.sub("[联系方式见来源页面]", text)[:limit]


def safe_url(value: object) -> str:
    url = clean_text(value, 1000)
    parsed = urlparse(url)
    return url if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _first(row: dict, field: str) -> object:
    for key in ALIASES[field]:
        value = row.get(key)
        if value not in (None, "", []):
            return value
    return ""


def normalize_profile(row: dict) -> dict | None:
    if not isinstance(row, dict):
        return None
    name = clean_text(_first(row, "name"), 100)
    institution = clean_text(_first(row, "institution"), 160)
    if not name or not institution:
        return None
    homepage = safe_url(_first(row, "homepage"))
    raw_discipline = clean_text(_first(row, "discipline"), 160)
    discipline = LEGACY_DIRECTIONS.get(raw_discipline, raw_discipline)
    first_level = clean_text(_first(row, "first_level_discipline"), 160)
    if not first_level:
        first_level = "集成电路专题（一级学科待核定）" if raw_discipline in LEGACY_DIRECTIONS else discipline
    direction_group = clean_text(_first(row, "direction_group"), 160)
    if not direction_group:
        direction_group = discipline if raw_discipline in LEGACY_DIRECTIONS else re.split(
            r"[、,，;；/]", clean_text(_first(row, "interests"), 600), maxsplit=1,
        )[0].strip() or "方向待补"
    supplied_sources = row.get("sources") if isinstance(row.get("sources"), list) else []
    sources = []
    for source in supplied_sources[:20]:
        if not isinstance(source, dict):
            continue
        url = safe_url(source.get("url"))
        if url:
            sources.append({
                "id": uuid.uuid4().hex,
                "url": url,
                "title": clean_text(source.get("title"), 160),
                "claim": clean_text(source.get("claim"), 1000),
                "status": "待人工核查",
                "added_at": now(),
            })
    if homepage and not any(s["url"] == homepage for s in sources):
        sources.insert(0, {
            "id": uuid.uuid4().hex,
            "url": homepage,
            "title": "提供的主页链接",
            "claim": "",
            "status": "待人工核查",
            "added_at": now(),
        })
    return {
        "id": uuid.uuid4().hex,
        "name": name,
        "institution": institution,
        "department": clean_text(_first(row, "department"), 160),
        "discipline": discipline,
        "first_level_discipline": first_level,
        "direction_group": direction_group,
        "interests": clean_text(_first(row, "interests"), 600),
        "summary": clean_text(_first(row, "summary"), 1000),
        "homepage": homepage,
        "sources": sources,
        "notes": "",
        "shortlisted": False,
        "imported_from": "手工录入",
        "added_at": now(),
    }


def parse_import(filename: str, content: str) -> list[dict]:
    if len(content) > 10_000_000:
        raise ValueError("导入文件超过 10 MB")
    if filename.lower().endswith(".json"):
        data = json.loads(content.lstrip("\ufeff"))
        rows = data.get("profiles", []) if isinstance(data, dict) else data
    elif filename.lower().endswith(".csv"):
        rows = list(csv.DictReader(io.StringIO(content.lstrip("\ufeff"))))
    else:
        raise ValueError("只支持 UTF-8 CSV 或 JSON 文件")
    if not isinstance(rows, list):
        raise ValueError("文件顶层应为数组，或含 profiles 数组")
    if len(rows) > MAX_IMPORT_ROWS:
        raise ValueError(f"单次最多导入 {MAX_IMPORT_ROWS} 条")
    return rows


def _project_path(project_id: str) -> Path:
    if not PROJECT_ID.fullmatch(project_id):
        raise ValueError("无效的项目 ID")
    return PROJECTS_DIR / f"{project_id}.json"


def save_project(project: dict) -> None:
    path = _project_path(project["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    project["updated_at"] = now()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def create_project(name: str) -> dict:
    title = clean_text(name, 120)
    if not title:
        raise ValueError("请填写项目名称")
    project = {"id": uuid.uuid4().hex, "name": title, "created_at": now(), "profiles": []}
    save_project(project)
    return project


def load_project(project_id: str) -> dict:
    path = _project_path(project_id)
    if not path.exists():
        raise FileNotFoundError("找不到这个项目")
    return json.loads(path.read_text(encoding="utf-8"))


def list_projects() -> list[dict]:
    if not PROJECTS_DIR.exists():
        return []
    projects = []
    for path in PROJECTS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            projects.append({
                "id": data["id"], "name": data["name"],
                "count": len(data.get("profiles", [])), "updated_at": data.get("updated_at", ""),
            })
        except (OSError, ValueError, KeyError):
            continue
    return sorted(projects, key=lambda x: x["updated_at"], reverse=True)


def import_profiles(project: dict, rows: list[dict], imported_from: str = "导入文件") -> dict:
    # 同名同单位可能是不同院系的人；只有全部识别字段相同才自动去重。
    def identity(profile: dict) -> tuple[str, str, str, str]:
        return tuple(profile[key].casefold() for key in
                     ("name", "institution", "department", "homepage"))

    existing = {identity(p) for p in project["profiles"]}
    added = skipped = duplicates = 0
    for row in rows:
        profile = normalize_profile(row)
        if profile is None:
            skipped += 1
            continue
        key = identity(profile)
        if key in existing:
            duplicates += 1
            continue
        profile["imported_from"] = clean_text(imported_from, 160)
        project["profiles"].append(profile)
        existing.add(key)
        added += 1
    save_project(project)
    return {"added": added, "skipped": skipped, "duplicates": duplicates, "total": len(project["profiles"])}
