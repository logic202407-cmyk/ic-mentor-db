"""录制前就绪检查：确认视频脚本里要演示的功能真的可用、且足够快。

为什么需要
----------
录视频是**一次性的**：如果现场点「载入合成演示」报错，或者点「AI 语义检索」要等 95 MB 模型
下载，整段就要重录。这些都可以在录制前用脚本验证。

本工具检查四件事：

1. 服务在跑、健康检查通过；
2. `/api/demo` 能载入 10 条虚构演示资料（视频镜头 2 依赖它）；
3. 语义检索**命中本地缓存**且响应足够快（镜头 9 依赖它；缓存缺失会触发模型下载）；
4. 演示用的深链能打开（镜头 5/7 依赖它）。

用法::

    python -m workbench.tools.recording_readiness

退出码：全部就绪 0，否则 1。
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8765"


def call(path: str, method: str = "GET", payload: dict | None = None,
         timeout: int = 120) -> tuple[int, object, float]:
    url = BASE + path
    data = None
    # 工作台的写请求要求带 Origin（防 DNS rebinding / 跨站表单）。本工具是本地命令行，
    # 不是浏览器，必须显式声明自己就是本机页面这一来源；否则会被 403 拦下。
    headers = {"Content-Type": "application/json", "Origin": BASE}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            body = fh.read().decode("utf-8", "replace")
            elapsed = time.time() - started
            try:
                return fh.status, json.loads(body), elapsed
            except ValueError:
                return fh.status, body, elapsed
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:200], time.time() - started
    except Exception as exc:  # noqa: BLE001 - 连不上也要给出可读结论
        return 0, f"{type(exc).__name__}: {exc}", time.time() - started


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    status, health, _ = call("/api/health", timeout=15)
    checks.append(("服务在运行", status == 200, f"status={status}"))

    status, demo, elapsed = call("/api/demo", method="POST", payload={})
    n_profiles = 0
    if status == 200 and isinstance(demo, (dict, list)):
        if isinstance(demo, dict):
            n_profiles = len(demo.get("profiles") or [])
        else:
            n_profiles = len(demo)
    checks.append((
        "合成演示可载入",
        status == 200 and n_profiles >= 8,
        f"status={status} profiles={n_profiles} {elapsed:.1f}s",
    ))

    # 语义检索：需要项目 id
    project_id = ""
    if isinstance(demo, dict):
        project_id = str(demo.get("id") or "")
    if project_id:
        status, res, elapsed = call(
            f"/api/projects/{project_id}/search",
            method="POST",
            payload={"query": "中文问答和知识组织", "mode": "semantic", "limit": 5},
            timeout=180,
        )
        hits = 0
        model = ""
        if status == 200 and isinstance(res, dict):
            hits = len(res.get("results") or [])
            model = str(res.get("model") or "")
        checks.append((
            "语义检索可用且已缓存",
            status == 200 and hits > 0,
            f"status={status} hits={hits} {elapsed:.2f}s model={model}",
        ))
        checks.append((
            "语义检索响应够快（<3s，说明命中本机缓存）",
            status == 200 and elapsed < 3.0,
            f"{elapsed:.2f}s",
        ))
    else:
        checks.append(("语义检索可用且已缓存", False, "拿不到演示项目 id"))

    # 深链：优先用本地截图工具留下的目标，没有就现挑一位（与 ui_smoke 同一套逻辑），
    # 这样干净 clone 上也能跑这项检查，不会因为少一个本地临时文件就整体报错。
    target = Path(".workbench-data/_shot_target.txt")
    mentor_id = ""
    if target.is_file():
        mentor_id = target.read_text(encoding="utf-8").strip()
    if not mentor_id:
        try:
            from .ui_smoke import pick_mentor
            mentor_id = pick_mentor()
        except SystemExit:
            mentor_id = ""
    if mentor_id:
        html = urllib.request.urlopen(f"{BASE}/?mentor={mentor_id}", timeout=60).read().decode(
            "utf-8", "replace")
        checks.append(("详情页深链可打开", "mentorTitle" in html, f"mentor={mentor_id}"))
    else:
        checks.append(("详情页深链可打开", False, "没有可用的导师 id（先跑 AI 产物或放 _shot_target.txt）"))

    ok = all(passed for _n, passed, _d in checks)
    lines = ["录制前就绪检查", ""]
    for name, passed, detail in checks:
        lines.append(f"  {'PASS' if passed else 'FAIL'}  {name}  [{detail}]")
    lines.append("")
    lines.append("结论: " + ("可以开录" if ok else "先修问题再录"))
    text = "\n".join(lines)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", "replace"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
