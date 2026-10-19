"""Local web API for the cross-discipline mentor research workbench."""

from __future__ import annotations

import csv
import json
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .core import (
    ROOT, clean_text, create_project, import_profiles, list_projects,
    load_project, normalize_profile, now, parse_import, safe_url, save_project,
)
from .search import MODEL_NAME, search
from . import ai_hints, catalog, investigation, relations, student_score
from .openalex import OpenAlexUnavailable, author_candidates
import requests

app = FastAPI(title="导师调查工作台", docs_url=None, redoc_url=None)
WEB = Path(__file__).resolve().parent / "web" / "desk.html"
CLASSIC_WEB = Path(__file__).resolve().parent / "web" / "index.html"
DEMO = ROOT / "workbench" / "examples" / "cross_discipline_demo.json"
app.mount("/assets", StaticFiles(directory=WEB.parent / "assets"), name="assets")


@app.middleware("http")
async def local_origin(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin", "")
        if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
            return JSONResponse({"detail": "仅允许从本地工作台页面提交"}, status_code=403)
    return await call_next(request)


def _project(project_id: str) -> dict:
    try:
        return load_project(project_id)
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def _profile(project: dict, profile_id: str) -> dict:
    for profile in project["profiles"]:
        if profile["id"] == profile_id:
            return profile
    raise HTTPException(status_code=404, detail="找不到这位导师")


@app.get("/")
def home():
    return FileResponse(WEB, media_type="text/html")


@app.get("/classic")
def classic_workbench():
    return FileResponse(CLASSIC_WEB, media_type="text/html")


@app.get("/legacy/network")
def legacy_network():
    return FileResponse(ROOT / "reports" / "导师关系网络.html", media_type="text/html")


@app.get("/api/health")
def health():
    return {"ok": True, "model": MODEL_NAME, "storage": "local"}


@app.get("/api/catalog/name")
def catalog_name(q: str = "", project_id: str = "", include_non_engineering: bool = False):
    try:
        return catalog.search_name(q, project_id, include_non_engineering=include_non_engineering)
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/catalog/scope")
def catalog_scope():
    return catalog.scope_info()


@app.get("/api/catalog/relations/summary")
def catalog_relations_summary():
    return relations.summary()


@app.get("/api/catalog/disciplines")
def catalog_disciplines(project_id: str = "", include_non_engineering: bool = False):
    try:
        return catalog.disciplines(project_id, include_non_engineering)
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/catalog/institutions")
def catalog_institutions(discipline: str, project_id: str = "",
                         include_non_engineering: bool = False):
    try:
        return catalog.institutions(discipline, project_id, include_non_engineering)
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/catalog/directions")
def catalog_directions(discipline: str, institution: str, project_id: str = "",
                       include_non_engineering: bool = False):
    try:
        return catalog.directions(discipline, institution, project_id, include_non_engineering)
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/catalog/mentors")
def catalog_mentors(discipline: str, institution: str, direction: str, project_id: str = "",
                    include_non_engineering: bool = False):
    try:
        return catalog.mentors(discipline, institution, direction, project_id,
                               include_non_engineering)
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/catalog/coverage")
def catalog_coverage():
    return catalog.coverage()


@app.get("/api/catalog/mentor/{mentor_id}/report.md")
def catalog_report(mentor_id: str):
    try:
        body = catalog.report_markdown(mentor_id).encode("utf-8")
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(body, media_type="text/markdown; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="mentor-investigation-{mentor_id[:20]}.md"',
    })


@app.get("/api/catalog/ai-hints")
def catalog_ai_hints():
    """AI 两处「待复核」结果的概览；产物未生成时各计数为 0，不报错。"""
    return ai_hints.summary()


@app.get("/api/catalog/mentor/{mentor_id}/ai-hints")
def catalog_mentor_ai_hints(mentor_id: str):
    """某位导师的方向建议与同名待核提示。

    这些只是**建议**：不写回任何原始字段，也不参与参考分与关系分析。
    """
    return ai_hints.hints_for(mentor_id)


@app.get("/api/catalog/mentor/{mentor_id}")
def catalog_dossier(mentor_id: str):
    result = catalog.dossier(mentor_id)
    if result is None:
        raise HTTPException(status_code=404, detail="找不到这位导师")
    # The student-facing reference score and the layered relationship view are
    # attached here so every caller sees the same basis text and caveats.
    key = result.get("network_key") or (result.get("profile") or {}).get("network_key")
    result["student_score"] = student_score.compute(key)
    result["relations_analysis"] = relations.analyze(key)
    return result


@app.post("/api/catalog/mentor/{mentor_id}/public-research")
def refresh_public_research(mentor_id: str):
    from .public_research import enrich
    try:
        return enrich(mentor_id, force=True, refresh_pages=True)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.patch("/api/catalog/mentor/{mentor_id}/case")
async def catalog_case(mentor_id: str, request: Request):
    try:
        return catalog.update_case(mentor_id, await request.json())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/catalog/mentor/{mentor_id}/investigation")
def investigation_overview(mentor_id: str):
    try:
        return investigation.overview(mentor_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/catalog/mentor/{mentor_id}/investigation")
async def start_investigation(mentor_id: str, request: Request):
    data = await request.json()
    try:
        return await run_in_threadpool(investigation.run, mentor_id,
                                      data.get("modules", []), data.get("paper_ids", []))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/catalog/mentor/{mentor_id}/evidence")
async def catalog_add_evidence(mentor_id: str, request: Request):
    try:
        return catalog.add_evidence(mentor_id, await request.json())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/catalog/mentor/{mentor_id}/papers")
async def catalog_add_paper(mentor_id: str, request: Request):
    try:
        return catalog.add_paper(mentor_id, await request.json())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.delete("/api/catalog/mentor/{mentor_id}/papers/{paper_id}")
def catalog_remove_paper(mentor_id: str, paper_id: str):
    try:
        return catalog.remove_paper(mentor_id, paper_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.patch("/api/catalog/mentor/{mentor_id}/evidence/{evidence_id}")
async def catalog_update_evidence(mentor_id: str, evidence_id: str, request: Request):
    try:
        return catalog.update_evidence(mentor_id, evidence_id, (await request.json()).get("status", ""))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.delete("/api/catalog/mentor/{mentor_id}/evidence/{evidence_id}")
def catalog_remove_evidence(mentor_id: str, evidence_id: str):
    try:
        return catalog.remove_evidence(mentor_id, evidence_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/catalog/mentor/{mentor_id}/openalex/authors")
async def openalex_authors(mentor_id: str):
    profile = catalog.entry_by_id(mentor_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="找不到这位导师")
    try:
        return {"results": await run_in_threadpool(author_candidates, profile["name"])}
    except OpenAlexUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except requests.RequestException as error:
        raise HTTPException(status_code=503, detail="OpenAlex 暂不可用，请稍后重试；本地调查记录未受影响。") from error


@app.post("/api/catalog/mentor/{mentor_id}/openalex/refresh")
async def openalex_refresh(mentor_id: str):
    try:
        return await run_in_threadpool(catalog.refresh_openalex, mentor_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except OpenAlexUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except requests.RequestException as error:
        raise HTTPException(status_code=503, detail="OpenAlex 暂不可用，请稍后重试；本地调查记录未受影响。") from error


@app.get("/api/projects")
def projects():
    return list_projects()


@app.post("/api/projects")
async def new_project(request: Request):
    data = await request.json()
    try:
        return create_project(data.get("name", ""))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/demo")
def create_demo():
    data = json.loads(DEMO.read_text(encoding="utf-8"))
    project = create_project("跨专业演示项目（合成资料）")
    import_profiles(project, data["profiles"], "跨专业合成演示")
    return project


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    return _project(project_id)


@app.post("/api/projects/{project_id}/import")
async def import_file(project_id: str, request: Request):
    project = _project(project_id)
    data = await request.json()
    try:
        rows = parse_import(str(data.get("filename", "")), str(data.get("content", "")))
        return import_profiles(project, rows, str(data.get("filename", "导入文件")))
    except (ValueError, json.JSONDecodeError, csv.Error) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/projects/{project_id}/profiles")
async def add_profile(project_id: str, request: Request):
    project = _project(project_id)
    profile = normalize_profile(await request.json())
    if not profile:
        raise HTTPException(status_code=400, detail="请填写姓名和机构")
    if any(all(existing.get(key) == profile.get(key) for key in ("name", "institution", "department", "homepage"))
           for existing in project["profiles"]):
        raise HTTPException(status_code=409, detail="这位导师已经在当前资料夹中，可按姓名查找")
    project["profiles"].append(profile)
    save_project(project)
    return profile


@app.patch("/api/projects/{project_id}/profiles/{profile_id}")
async def update_profile(project_id: str, profile_id: str, request: Request):
    project = _project(project_id)
    profile = _profile(project, profile_id)
    data = await request.json()
    if "notes" in data:
        profile["notes"] = clean_text(data["notes"], 1000)
    if "shortlisted" in data:
        profile["shortlisted"] = bool(data["shortlisted"])
    save_project(project)
    return profile


@app.post("/api/projects/{project_id}/profiles/{profile_id}/sources")
async def add_source(project_id: str, profile_id: str, request: Request):
    project = _project(project_id)
    profile = _profile(project, profile_id)
    data = await request.json()
    url = safe_url(data.get("url"))
    if not url:
        raise HTTPException(status_code=400, detail="请提供 http 或 https 来源链接")
    source = {
        "id": uuid.uuid4().hex,
        "url": url,
        "title": clean_text(data.get("title"), 160),
        "claim": clean_text(data.get("claim"), 1000),
        "status": "待人工核查",
        "added_at": now(),
    }
    profile["sources"].append(source)
    save_project(project)
    return source


@app.patch("/api/projects/{project_id}/profiles/{profile_id}/sources/{source_id}")
async def update_source(project_id: str, profile_id: str, source_id: str, request: Request):
    project = _project(project_id)
    profile = _profile(project, profile_id)
    source = next((s for s in profile["sources"] if s["id"] == source_id), None)
    if source is None:
        raise HTTPException(status_code=404, detail="找不到这条来源")
    data = await request.json()
    if data.get("status") not in {"待人工核查", "已人工核查"}:
        raise HTTPException(status_code=400, detail="无效的核查状态")
    source["status"] = data["status"]
    source["checked_at"] = now() if data["status"] == "已人工核查" else None
    save_project(project)
    return source


@app.post("/api/projects/{project_id}/search")
async def find_profiles(project_id: str, request: Request):
    project = _project(project_id)
    data = await request.json()
    try:
        results = await run_in_threadpool(
            search, project, str(data.get("query", "")), str(data.get("mode", "semantic")),
            int(data.get("limit", 20)), str(data.get("discipline", "")),
            str(data.get("institution", "")),
        )
        return {"results": results, "model": MODEL_NAME if data.get("mode", "semantic") == "semantic" else None}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"语义模型暂不可用：{error}") from error


@app.get("/api/projects/{project_id}/export")
def export_project(project_id: str):
    project = _project(project_id)
    body = json.dumps(project, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(body, media_type="application/json; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="mentor-workbench-{project_id[:8]}.json"',
    })
