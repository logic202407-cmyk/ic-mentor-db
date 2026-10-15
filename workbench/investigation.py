"""Bounded investigation tasks: assemble local evidence and check DOI metadata.

Task completion never marks a human review as complete. Remote metadata proves
that a record was found, not that a work belongs to the selected mentor.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, urlencode

import requests

from . import catalog, core

ARCHIVE_ROOT = Path(os.environ.get("MENTOR_ARCHIVE_DIR", core.ROOT.parent / "academic-investigations"))
ARCHIVES = {
    ("唐仙", "清华大学深圳国际研究生院"): "tang-xian",
    ("李福乐", "清华大学"): "li-fu-le",
    ("张学永", "东南大学"): "zhang-xue-yong",
    ("于维翰", "澳门大学"): "yu-wei-han",
}
MODULES = {
    "identity": "身份与来源", "papers": "论文候选整理",
    "relations": "关系证据整理", "archive": "既有调查档案",
    "crossref": "DOI 元数据核对",
}
DEFAULT_MODULES = ["identity", "papers", "relations", "archive"]
DOI = re.compile(r"^10\.\d{4,9}/[^\s]+$", re.I)


def normalize_doi(value: object) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", text, flags=re.I)
    return text.lower() if len(text) <= 250 and DOI.fullmatch(text) else ""


def paper_candidates(data: dict) -> list[dict]:
    """Keep provenance and deduplicate DOI aliases, without asserting authorship."""
    found = {}
    for origin, records in (("本地专题候选", data["papers"]),
                            ("手动添加", data["case"].get("manual_papers", [])),
                            ("用户选择的 OpenAlex 记录", (data["case"].get("openalex_snapshot") or {}).get("papers", []))):
        for record in records:
            doi = normalize_doi(record.get("doi"))
            title = core.clean_text(record.get("title"), 350)
            key = doi or re.sub(r"\W+", "", title.casefold())
            if not key:
                continue
            if key in found:
                if origin not in found[key]["origins"]:
                    found[key]["origins"].append(origin)
                continue
            found[key] = {"id": hashlib.sha256(key.encode()).hexdigest()[:20],
                          "doi": doi, "title": title, "year": record.get("year"),
                          "venue": core.clean_text(record.get("venue"), 160),
                          "url": core.safe_url(record.get("url")), "origins": [origin]}
    return list(found.values())


def archive_for(profile: dict) -> dict | None:
    slug = ARCHIVES.get((profile["name"], profile["institution"]))
    if not slug:
        return None
    directory = ARCHIVE_ROOT / slug / "data"
    path = directory / "profile.md"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    date = re.search(r"调查日期[：:]\s*(\d{4}-\d{2}-\d{2})", text)
    sections = []
    for title, body in re.findall(r"^## ([^\n]+)\n(.*?)(?=^## |\Z)", text, re.M | re.S):
        if title.strip() not in {"教育经历", "工作经历", "研究领域", "声称产出（需 Step 2 核实）"}:
            continue
        lines = [line for line in body.strip().splitlines()
                 if not re.search(r"邮箱|电话|房间|出生|性别|籍贯|@", line)]
        heading = "历史产出记录（待复核）" if title.strip().startswith("声称产出") else title.strip()
        sections.append({"title": heading, "text": "\n".join(lines)[:2400]})
    urls = list(dict.fromkeys(core.safe_url(url) for url in re.findall(r"\]\((https?://[^)]+)\)", text)))
    collaborators = []
    source = directory / "scholar_data.json"
    if source.is_file():
        stored = json.loads(source.read_text(encoding="utf-8"))
        for row in stored.get("relationship_network", {}).get("key_collaborators", [])[:20]:
            collaborators.append({"name": core.clean_text(row.get("name"), 100),
                                  "years": [year for year in row.get("years", []) if isinstance(year, int)]})
    return {"date": date.group(1) if date else "未知", "case_name": slug,
            "sections": sections, "source_urls": [url for url in urls if url],
            "collaborators": collaborators,
            "caveat": "来自旧导师调查项目的历史摘录，尚未重新访问原网页；任职、产出和关系均需复核。"}


def fingerprint(data: dict) -> str:
    case = data["case"]
    payload = {key: data[key] for key in ("profile", "papers", "relations")}
    # Built-in source IDs/import timestamps are generated at process startup.
    payload["sources"] = [{key: source.get(key) for key in ("url", "title", "claim", "status")}
                          for source in data["sources"]]
    payload["evidence"] = case.get("evidence", [])
    payload["manual_papers"] = case.get("manual_papers", [])
    payload["author"] = case.get("openalex_author_id", "")
    payload["snapshot"] = case.get("openalex_snapshot")
    payload["archive"] = archive_for(data["profile"])
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def review_guide(data: dict) -> dict:
    """Suggest next actions from saved human statuses, never certify a person."""
    evidence = data["case"].get("evidence", [])
    specifications = [
        ("身份与任职", "官方身份与任职", "overview", "核对来源", "打开本人或院系主页，对照姓名、院系和当前任职。"),
        ("研究方向", "研究方向", "overview", "查看方向", "对照官网研究主题与近期作品，记录变化和不一致之处。"),
        ("论文归属", "论文与成果", "papers", "核对论文", "按作者机构、研究主题和年份排除同名误配。"),
        ("论文原文核读", "论文与成果", "papers", "查看论文", "阅读可获得的原文，记录方法、证据和结论适用范围。"),
        ("学术关系", "学术关系", "network", "展开关系", "核对本人履历或独立来源；共同署名只保留为合作线索。"),
        ("招生与培养", "招生与培养", "overview", "查看招生线索", "查所在院系当年招生公告，名额与培养方式向本人确认。"),
        ("公开声明对照", "其他公开记录", "overview", "对照来源", "比较不同日期的公开表述，保留链接和原文语境。"),
        ("多源交叉核查", "其他公开记录", "overview", "查看证据", "确认关键事实是否有独立来源；转载同一页面不算独立佐证。"),
    ]
    items = []
    for section, category, pane, action, instruction in specifications:
        status = data["case"].get("section_status", {}).get(section, "待核查")
        count = sum(item.get("category") == category for item in evidence)
        available = f"本机已登记 {count} 条相关补充来源" if count else "尚未登记此类补充来源"
        if section == "身份与任职":
            available += f"；档案有 {len(data['sources'])} 条原始来源"
        if section in {"论文归属", "论文原文核读"}:
            available += f"；当前有 {len(paper_candidates(data))} 条论文候选"
        items.append({"section": section, "category": category, "pane": pane, "action": action,
                      "status": status, "instruction": instruction, "available": available})
    return {"items": items, "total": len(items),
            "reviewed": sum(item["status"] == "已人工核查" for item in items),
            "not_applicable": sum(item["status"] == "不适用" for item in items),
            "pending": sum(item["status"] in {"待核查", "需补证据"} for item in items)}


def overview(mentor_id: str) -> dict:
    data = catalog.dossier(mentor_id)
    if data is None:
        raise ValueError("找不到这位导师")
    papers = paper_candidates(data)
    last = data["case"].get("investigation_run")
    query = f'{data["profile"]["name"]} {data["profile"]["institution"]}'
    return {"modules": [{"id": key, "label": label, "default": key in DEFAULT_MODULES}
                        for key, label in MODULES.items()], "papers": papers,
            "last_run": last, "stale": bool(last and last.get("fingerprint") != fingerprint(data)),
            "review_guide": review_guide(data),
            "research_links": [{"label": label, "url": "https://www.bing.com/search?" + urlencode({"q": query + " " + keywords})}
                               for label, keywords in (("查找官方履历", "官网 教育经历"),
                                                       ("查找招生公告", "研究生 招生"),
                                                       ("查找项目与专利", "科研项目 专利"))]}


def _plain(value: object, limit: int = 350) -> str:
    return core.clean_text(re.sub(r"<[^>]+>", "", str(value or "")), limit)


def check_doi(paper: dict) -> dict:
    doi = normalize_doi(paper["doi"])
    result = {"doi": doi, "candidate_title": paper["title"], "checked_at": core.now(),
              "api_url": "https://api.crossref.org/works/" + quote(doi, safe=""),
              "status": "unknown", "message": "待查询"}
    try:
        response = requests.get(result["api_url"], timeout=8, allow_redirects=False,
                                headers={"User-Agent": "mentor-research-workbench/0.2"})
        if response.status_code == 404:
            return result | {"status": "not_found", "message": "Crossref 未返回此 DOI；可能不在该注册机构，不能据此认定论文不存在。"}
        if response.status_code in {429, 503}:
            return result | {"status": "unavailable", "message": "Crossref 限流或服务暂不可用；未完成核对。"}
        response.raise_for_status()
        message = response.json()["message"]
        if not isinstance(message, dict) or normalize_doi(message.get("DOI")) != doi:
            raise ValueError("unexpected DOI record")
        titles = message.get("title") or []
        title = _plain(titles[0] if titles else "")
        authors = [_plain(" ".join(filter(None, [a.get("given"), a.get("family")])) or a.get("name"))
                   for a in (message.get("author") or [])[:30]]
        compact = lambda value: re.sub(r"\W+", "", value.casefold())
        title_match = bool(title and paper["title"] and compact(title) == compact(paper["title"]))
        dates = (message.get("published") or {}).get("date-parts") or []
        return result | {"status": "found", "message": "找到 DOI 登记记录；作者归属仍需人工核查。",
                         "title": title, "title_exact_match": title_match, "authors": authors,
                         "year": dates[0][0] if dates and dates[0] else None,
                         "venue": _plain((message.get("container-title") or [""])[0], 160),
                         "url": "https://doi.org/" + quote(doi, safe="/")}
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return result | {"status": "unavailable", "message": "请求失败或响应不完整；未完成核对，可稍后重试。"}


def run(mentor_id: str, selected: list[str], paper_ids: list[str]) -> dict:
    if not isinstance(selected, list) or not selected or any(not isinstance(x, str) or x not in MODULES for x in selected):
        raise ValueError("请选择有效的调查模块")
    if not isinstance(paper_ids, list) or any(not isinstance(x, str) for x in paper_ids) or len(paper_ids) > 3:
        raise ValueError("每次最多核对 3 篇论文，请从已有候选中选择")
    data = catalog.dossier(mentor_id)
    if data is None:
        raise ValueError("找不到这位导师")
    papers = paper_candidates(data)
    by_id = {paper["id"]: paper for paper in papers if paper["doi"]}
    if any(key not in by_id for key in paper_ids):
        raise ValueError("论文候选已变化，请刷新后重新选择")
    selected = list(dict.fromkeys(selected))
    modules = []
    sources = data["sources"] + data["case"].get("evidence", [])
    for module in selected:
        item = {"id": module, "label": MODULES[module], "status": "已整理", "summary": "", "details": {}}
        if module == "identity":
            item["summary"] = f"已汇集 {len(sources)} 条登记来源；当前任职和招生资格仍需打开官网核查。"
            item["status"] = "已整理" if sources else "待补资料"
            item["details"] = {"sources": sources}
        elif module == "papers":
            counts = Counter(str(p["year"]) for p in papers if p.get("year"))
            item["summary"] = f"整理去重后有 {len(papers)} 条论文候选，其中 {sum(bool(p['doi']) for p in papers)} 条包含 DOI。这是当前展示样本，不能视为本人全部成果。"
            item["status"] = "已整理" if papers else "待选择作者记录"
            item["details"] = {"by_year": dict(sorted(counts.items())), "sample_count": len(papers)}
        elif module == "relations":
            counts = {key: len(data["relations"][key]) for key in ("advisor", "overlap", "collab", "sibling", "external")}
            coauthors = len((data["case"].get("openalex_snapshot") or {}).get("coauthors", []))
            item["summary"] = f"既有关系网展示 {sum(counts.values())} 条线索，OpenAlex 作品样本含 {coauthors} 位共同作者。推断和共同署名不证明指导关系。"
            item["status"] = "已整理" if sum(counts.values()) + coauthors else "待补资料"
            item["details"] = {"counts": counts, "sample_coauthors": coauthors}
        elif module == "archive":
            archive = archive_for(data["profile"])
            item["status"] = "历史资料待复核" if archive else "未找到匹配档案"
            item["summary"] = archive["caveat"] if archive else "未找到姓名和机构同时匹配的旧调查档案。"
            item["details"] = archive or {}
        elif module == "crossref":
            chosen = [by_id[key] for key in dict.fromkeys(paper_ids)]
            if not chosen:
                item["status"], item["summary"] = "等待选择论文", "勾选最多 3 篇已有 DOI 的论文后再开始。"
                item["details"] = {"checks": []}
            else:
                with ThreadPoolExecutor(max_workers=3) as pool:
                    checks = list(pool.map(check_doi, chosen))
                found = sum(check["status"] == "found" for check in checks)
                item["status"] = "已返回元数据" if found == len(checks) else "存在待核对项"
                item["summary"] = f"查询 {len(checks)} 篇，找到 {found} 条 DOI 登记记录；这不自动确认作者身份、论文质量或内容真实性。"
                item["details"] = {"checks": checks}
        modules.append(item)
    result = {"id": uuid.uuid4().hex, "created_at": core.now(), "modules": modules,
              "fingerprint": fingerprint(data), "selected": selected,
              "caveat": "模块状态只描述本次资料整理和查询结果，人工核查状态不会自动改变。"}
    # Reload to preserve notes/evidence edited while a remote call was running.
    record = catalog.load_case(mentor_id)
    record["investigation_run"] = result
    record["updated_at"] = core.now()
    catalog._write_case(record)
    return result
