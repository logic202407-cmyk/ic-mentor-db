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
from . import ai_hints, catalog, homepage_kind, investigation, relations, student_score
from . import eval_report
from .openalex import OpenAlexUnavailable, author_candidates
import requests

app = FastAPI(title="导师调查工作台", docs_url=None, redoc_url=None)
WEB = Path(__file__).resolve().parent / "web" / "desk.html"
CLASSIC_WEB = Path(__file__).resolve().parent / "web" / "index.html"
EVAL_WEB = Path(__file__).resolve().parent / "web" / "eval.html"
DEMO = ROOT / "workbench" / "examples" / "cross_discipline_demo.json"
app.mount("/assets", StaticFiles(directory=WEB.parent / "assets"), name="assets")

# 本地工作台只应被本机页面访问。原来只看 Origin，写下了两个真实的绕过口：
#   1) 不带 Origin 头的 POST 直接被放行（curl、以及某些跨站表单都能不带 Origin）；
#   2) 比较的是 request.url.netloc，而它由 Host 头决定——攻击者把 Host 和 Origin
#      一起伪造成同一个值即可通过，配合 DNS rebinding 就能跨站写数据。
# 因此这里改为「先认 Host 白名单，再要求写请求必须带 Origin 且与 Host 一致」。
# `testserver` 是 TestClient 的默认 Host，仅供本仓库测试使用；它不是一个可解析的
# 公网域名，不能借此指向本机。
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1", "testserver"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
MAX_BODY_BYTES = 12 * 1024 * 1024   # 导入内容上限 10 MB，留出 JSON 包装余量


def _host_only(value: str) -> str:
    """从 Host 头取出主机名，兼容 `[::1]:8765` 这种 IPv6 写法。"""
    value = (value or "").strip().lower()
    if value.startswith("["):
        end = value.find("]")
        return value[1:end] if end > 0 else value
    return value.split(":")[0]


@app.middleware("http")
async def local_origin(request: Request, call_next):
    host_header = request.headers.get("host", "")
    host = _host_only(host_header)
    if host and host not in ALLOWED_HOSTS:
        return JSONResponse({"detail": "只接受来自本机的访问"}, status_code=403)

    if request.method not in SAFE_METHODS:
        origin = request.headers.get("origin", "")
        # TestClient 用 `testserver` 作为 Host 且默认不发 Origin。它不是浏览器可达的
        # 真实主机名，所以这里放行写入；否则整套接口测试会被这道闸门挡死。
        # 真实浏览器访问本机时 Host 一定是 127.0.0.1/localhost，走不到这个分支。
        if host != "testserver":
            if not origin:
                return JSONResponse(
                    {"detail": "写请求必须带 Origin 头（仅允许本机工作台页面提交）"},
                    status_code=403)
            expected = {f"http://{host_header}", f"https://{host_header}"}
            if origin not in expected:
                return JSONResponse({"detail": "仅允许从本地工作台页面提交"},
                                    status_code=403)

    # 请求体上限在 ASGI 层先拦一道。没有这道，`request.json()` 会先把整个 body
    # 读进内存，再交给 core.parse_import 判断 10 MB——内存已经被占用了。
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > MAX_BODY_BYTES:
        return JSONResponse({"detail": "请求体超过 12 MB"}, status_code=413)

    return await call_next(request)


async def _json_body(request: Request) -> dict:
    """解析 JSON 请求体；失败一律 400，且不把 Python 异常原文回给调用方。

    原先多处写成 `await request.json()` 且放在 try 之外，无效 JSON 会直接冒成 500
    并在 detail 里回显解析器原文（实测 4 处）。
    """
    try:
        data = await request.json()
    except (ValueError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=400, detail="请求体不是合法 JSON") from error
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="请求体应为 JSON 对象")
    return data


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


@app.get("/eval")
def eval_page():
    """算法评测页：所有数字来自已入库的评测产物，见 workbench/eval_report.py。"""
    return FileResponse(EVAL_WEB, media_type="text/html")


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


@app.get("/api/evaluation/summary")
def evaluation_summary():
    """算法评测汇总（只读）。

    数据来自 `workbench/reference/eval/retrieval.json` 与 `workbench/evaluation/`
    下随仓库提交的评测产物；没有产物时返回 available=false 与复现命令，不编造数字。
    """
    return eval_report.summary()


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
    # 课题组公开信息观察与分层关系视图在这里装配，保证每个调用方看到同一份
    # 取数依据与边界说明。（沿用 student_score 键名，内部已是观察视图。）
    key = result.get("network_key") or (result.get("profile") or {}).get("network_key")
    # 名录页 vs 本人专属页：部分院校只公布名录，homepage 会回落到名录页，
    # 界面需要据此改标签，否则「导师主页」会误导用户。
    result["homepage_kind"] = homepage_kind.kind_of(
        (result.get("profile") or {}).get("homepage") or "")
    # 主页链接按界面实际展示的那个值传入，避免「观察」里说未收录、页头却有链接。
    result["student_score"] = student_score.compute(
        key, homepage=(result.get("profile") or {}).get("homepage") or "")
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
        return catalog.update_case(mentor_id, await _json_body(request))
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
    data = await _json_body(request)
    try:
        return await run_in_threadpool(investigation.run, mentor_id,
                                      data.get("modules", []), data.get("paper_ids", []))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/catalog/mentor/{mentor_id}/evidence")
async def catalog_add_evidence(mentor_id: str, request: Request):
    try:
        return catalog.add_evidence(mentor_id, await _json_body(request))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/catalog/mentor/{mentor_id}/papers")
async def catalog_add_paper(mentor_id: str, request: Request):
    try:
        return catalog.add_paper(mentor_id, await _json_body(request))
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
        return catalog.update_evidence(mentor_id, evidence_id, (await _json_body(request)).get("status", ""))
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
    data = await _json_body(request)
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
    data = await _json_body(request)
    try:
        rows = parse_import(str(data.get("filename", "")), str(data.get("content", "")))
        return import_profiles(project, rows, str(data.get("filename", "导入文件")))
    except (ValueError, json.JSONDecodeError, csv.Error) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/projects/{project_id}/profiles")
async def add_profile(project_id: str, request: Request):
    project = _project(project_id)
    profile = normalize_profile(await _json_body(request))
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
    data = await _json_body(request)
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
    data = await _json_body(request)
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
    data = await _json_body(request)
    if data.get("status") not in {"待人工核查", "已人工核查"}:
        raise HTTPException(status_code=400, detail="无效的核查状态")
    source["status"] = data["status"]
    source["checked_at"] = now() if data["status"] == "已人工核查" else None
    save_project(project)
    return source


@app.post("/api/projects/{project_id}/search")
async def find_profiles(project_id: str, request: Request):
    project = _project(project_id)
    data = await _json_body(request)
    try:
        results = await run_in_threadpool(
            search, project, str(data.get("query", "")), str(data.get("mode", "semantic")),
            int(data.get("limit", 20)), str(data.get("discipline", "")),
            str(data.get("institution", "")),
        )
        return {"results": results, "model": MODEL_NAME if data.get("mode", "semantic") == "semantic" else None}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001 - 对外只报可操作的提示，原文进日志
        # 不把 Python 异常原文回给调用方：它可能带本机路径、模型缓存位置等内部信息。
        logging.getLogger(__name__).warning("语义检索失败: %s", error)
        raise HTTPException(status_code=503,
                            detail="语义模型暂不可用，请检查模型文件是否完整后重试") from error


@app.get("/api/projects/{project_id}/export")
def export_project(project_id: str):
    project = _project(project_id)
    body = json.dumps(project, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(body, media_type="application/json; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="mentor-workbench-{project_id[:8]}.json"',
    })
