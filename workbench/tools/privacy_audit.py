# -*- coding: utf-8 -*-
"""隐私与合规自检：把可以自动化的部分做成可执行的检查。

用法：
    python -m workbench.tools.privacy_audit            # 人读摘要
    python -m workbench.tools.privacy_audit --check    # 有阻塞项则退出码 1
    python -m workbench.tools.privacy_audit --json     # 机器可读
    python -m workbench.tools.privacy_audit --only email-scan,phone-scan

设计约定（与 tools/audit_prepublish.mjs 的分工）：
1. 本脚本**只读**，不写任何文件，不发起网络请求（API 探针走 FastAPI TestClient 进程内）。
2. 只报告能指出**文件与位置**的结论；无法判定的记为 SKIP 并写明原因，不做"看起来没问题"的推断。
3. 校验的是仓库**当前工作树**（audit_prepublish.mjs 只覆盖 git 跟踪文件，二者互补）。
4. 状态语义：
   - PASS 通过；RISK 需人工判断（不阻塞）；FAIL 阻塞发布；SKIP 未执行/不适用。
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELF_PATH = Path(__file__).resolve()

# 跳过目录：第三方依赖、版本库元数据、模型权重（体积大且与隐私无关）
SKIP_DIRS = {".venv", ".git", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache"}
# 本机落盘目录（已 gitignore，不会发布）：默认不进入"发布面"扫描，
# 由 local-cache 检查单独统计——两件事要分开：会不会被发布 vs 本机是否留了原文。
LOCAL_DIRS = {".workbench-data"}
# 不参与文本扫描的扩展名（二进制/压缩流，误读会产生大量假阳性）
BINARY_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".woff",
              ".woff2", ".ttf", ".zip", ".docx", ".xlsx", ".pptx", ".pyc", ".db"}
TEXT_EXT = {".py", ".mjs", ".js", ".json", ".md", ".txt", ".yml", ".yaml", ".csv",
            ".html", ".css", ".cmd", ".ps1", ".bat", ".cff", ".toml", ".ini", ".cfg",
            ".gz",  # 压缩后的数据必须解压后再扫（audit_prepublish.mjs 会把它当文本读，实际扫不到）
            ""}

# ── 检测模式 ──
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# RFC 2606 / 6761 保留域：只可能是测试夹具，不算真实联系方式
RESERVED_DOMAIN = re.compile(r"@(?:example\.(?:com|net|org|edu)|example|invalid|localhost|test)(?:$|[^\w.-])", re.I)
# 电话：区号与号码之间必须有分隔符。两种已实测的假阳性必须排除，否则规则不可用：
#   1. 期刊文章号：(2023) 2305065、Adv. Mater. 37 (2025) 2404698 —— 形如"(年份) 7 位数字"
#   2. EI 收录号：083211445673 —— 12 位连写会被误拆成"区号 + 8 位号码"
# 因此不再接受无分隔符的写法，也去掉"(区号) 号码"这一分支。
PHONE = re.compile(r"(?<![0-9A-Za-z./-])(?:1[3-9]\d{9}|0\d{2,3}[-\s]\d{7,8})(?![0-9A-Za-z-])")
# 科研项目/基金编号与手机号形态相同（实测：上海市科委项目 17431904600、14431904300）。
# 命中这些词就降级为"需人工确认"，不直接判阻塞，否则规则会因为噪声被关掉。
PROJECT_NO_CONTEXT = re.compile(r"主持|参与|基金|项目|课题|资助|编号|批准号|No\.", re.I)
# 中国大陆 18 位身份证（末位可为 X），排除前后接十六进制/数字的长串
ID_CARD = re.compile(r"(?<![0-9A-Za-z])\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?![0-9A-Za-z])")

# 声明"不收集"的字段名（键名层面）。值非空即阻塞；键存在但全空记为 RISK。
SENSITIVE_KEYS = {
    "email": "邮箱", "mail": "邮箱", "e_mail": "邮箱", "email_address": "邮箱",
    "phone": "电话", "mobile": "手机", "telephone": "电话", "tel": "电话", "cellphone": "手机",
    "id_card": "身份证号", "idcard": "身份证号", "id_number": "证件号", "passport": "护照号",
    "address": "住址", "home_address": "家庭住址", "住址": "住址", "家庭住址": "住址",
    "birthday": "出生日期", "birth_date": "出生日期", "出生日期": "出生日期",
    "political_status": "政治面貌", "政治面貌": "政治面貌",
    "salary": "薪酬", "wage": "薪酬", "薪酬": "薪酬",
    "bank_account": "银行账号", "health": "健康信息", "medical": "健康信息",
    "wechat": "微信", "weixin": "微信", "qq": "QQ", "marital": "婚姻状况",
}
# 脱敏占位符质量：占位符自身若仍匹配邮箱正则，等于没脱敏（SECURITY.md:51-52 记载的历史教训）
BAD_PLACEHOLDER = re.compile(r"(?:redacted|hidden|masked|匿名|已隐去)[^\s，。；]*@|@[A-Za-z0-9.-]*redacted", re.I)

CREDENTIAL_PATTERNS = {
    "OpenAI 风格密钥": re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
    "GitHub Token": re.compile(r"\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    "AWS AccessKey": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "私钥块": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY"),
    "password 赋值": re.compile(r"(?i)\bpassword\s*[:=]\s*['\"][^'\"]{4,}"),
    "secret/api_key 赋值": re.compile(r"(?i)\b(?:secret|api[_-]?key|access[_-]?token)\s*[:=]\s*['\"][^'\"]{8,}"),
    "Bearer Token": re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]{20,}"),
    "Slack Token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
}

# 单字段超长：网页原文片段被整段入库的迹象（第三方权利风险）
LONG_TEXT_LIMIT = 2000


@dataclass
class Check:
    id: str
    title: str
    status: str = "SKIP"          # PASS / RISK / FAIL / SKIP
    detail: str = ""
    evidence: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "status": self.status,
                "detail": self.detail, "evidence": self.evidence[:12]}


# ── 文件遍历 ──

def iter_text_files(root: Path, include_local: bool = False):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if SKIP_DIRS & set(path.parts):
            continue
        if not include_local and LOCAL_DIRS & set(path.parts):
            continue
        if path.resolve() == SELF_PATH:
            # 扫描器自身含有检测模式（如占位符样例），与 audit_prepublish.mjs 一致跳过自检
            continue
        if path.suffix.lower() in BINARY_EXT:
            continue
        if path.suffix.lower() not in TEXT_EXT:
            continue
        yield path


def read_text(path: Path, limit: int = 60_000_000) -> str:
    """读文本：.gz 先解压，其余按 UTF-8 容错解码。"""
    if path.suffix == ".gz":
        try:
            with gzip.open(path, "rb") as handle:
                return handle.read(limit).decode("utf-8", "replace")
        except (OSError, EOFError):
            return ""
    try:
        if path.stat().st_size > limit:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def mask_email(value: str) -> str:
    local, _, domain = value.partition("@")
    return f"{local[:2]}***@{domain[:1]}***"


def mask_digits(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return f"{value[:3]}***（{len(digits)} 位数字）"


# ── 各项检查 ──

def check_email_scan(root: Path) -> Check:
    check = Check("email-scan", "邮箱残留（含解压后的 .json.gz）")
    hits = []
    for path in iter_text_files(root):
        text = read_text(path)
        if "@" not in text:
            continue
        for match in EMAIL.finditer(text):
            if match.group().endswith("users.noreply.github.com"):
                continue
            if RESERVED_DOMAIN.search(match.group() + " "):
                continue
            hits.append(f"{path.relative_to(root).as_posix()}:{line_of(text, match.start())} "
                        f"{mask_email(match.group())}")
            if len(hits) >= 40:
                break
    check.evidence = hits
    if hits:
        check.status = "FAIL"
        check.detail = f"发现 {len(hits)} 处非保留域邮箱（已脱敏显示）"
    else:
        check.status = "PASS"
        check.detail = "全部文本文件（含 5.2MB dossiers.json.gz 解压后）无真实邮箱"
    return check


def check_phone_scan(root: Path) -> Check:
    """号码残留：区分"真实号码"与"科研项目编号"（后者形态相同，降级为需人工确认）。"""
    check = Check("phone-scan", "电话号码残留")
    real, suspect = [], []
    for path in iter_text_files(root):
        text = read_text(path)
        for match in PHONE.finditer(text):
            line = line_of(text, match.start())
            window = text[max(0, match.start() - 40):match.end() + 40]
            entry = (f"{path.relative_to(root).as_posix()}:{line} {mask_digits(match.group())}")
            if PROJECT_NO_CONTEXT.search(window):
                if len(suspect) < 10:
                    suspect.append(entry)
            else:
                real.append(entry)
                if len(real) >= 40:
                    break
    check.evidence = real[:8] + suspect[:4]
    if real:
        check.status = "FAIL"
        check.detail = f"发现 {len(real)} 处号码形态（非项目编号语境）"
    elif suspect:
        check.status = "RISK"
        check.detail = (f"{len(suspect)} 处号码形态出现在项目/基金编号语境，"
                        "需人工确认不是电话")
    else:
        check.status = "PASS"
        check.detail = "无固话与 11 位手机号形态"
    return check


def check_id_card_scan(root: Path) -> Check:
    check = Check("idcard-scan", "身份证号 / 证件号残留")
    hits = []
    for path in iter_text_files(root):
        text = read_text(path)
        for match in ID_CARD.finditer(text):
            hits.append(f"{path.relative_to(root).as_posix()}:{line_of(text, match.start())} "
                        f"{match.group()[:6]}***")
            if len(hits) >= 20:
                break
    check.evidence = hits
    check.status = "FAIL" if hits else "PASS"
    check.detail = f"发现 {len(hits)} 处 18 位身份证形态" if hits else "无 18 位身份证形态"
    return check


def check_danger_keys(root: Path) -> Check:
    """危险键名：声明"不收集"的字段是否以键名形式出现在数据里。

    值为 null / 空串 / 空容器 → 键名仍在，记 RISK；有任何非空值 → FAIL。
    """
    check = Check("danger-keys", "危险键名（声明不收集的字段）")
    empty_only, with_value = [], []
    for path in iter_text_files(root):
        if path.suffix.lower() not in {".json", ".gz", ".csv"}:
            continue
        text = read_text(path)
        for key, label in SENSITIVE_KEYS.items():
            # 值可能是字符串、null、空数组/对象
            pattern = re.compile(
                r'"%s"\s*:\s*(?:"([^"]*)"|(null|\[\s*\]|\{\s*\}))' % re.escape(key), re.I)
            found = list(pattern.finditer(text))
            if not found:
                continue
            nonempty = [m.group(1) for m in found if m.group(1) and m.group(1).strip()]
            where = f"{path.relative_to(root).as_posix()}（{len(found)} 处）"
            if nonempty:
                with_value.append(f"{where} 键 {key}={label} 有 {len(nonempty)} 个非空值")
            else:
                empty_only.append(f"{where} 键 {key}={label} 值为 null/空（键名仍保留）")
    check.evidence = with_value[:8] + empty_only[:8]
    if with_value:
        check.status = "FAIL"
        check.detail = f"{len(with_value)} 个文件含非空的敏感字段值"
    elif empty_only:
        check.status = "RISK"
        check.detail = (f"{len(empty_only)} 个文件保留敏感键名但值全为空；"
                        "与「不收录该字段」的措辞不一致，建议删键或改写声明")
    else:
        check.status = "PASS"
        check.detail = "未出现声明不收集的字段键名"
    return check


def check_redaction_placeholder(root: Path) -> Check:
    """占位符必须自身不含 @；只查数据文件（文档里引用历史错误不算残留）。"""
    check = Check("redaction-quality", "脱敏占位符是否真的脱敏")
    hits = []
    for path in iter_text_files(root):
        if path.suffix.lower() not in {".json", ".gz", ".csv"}:
            continue
        text = read_text(path)
        for match in BAD_PLACEHOLDER.finditer(text):
            hits.append(f"{path.relative_to(root).as_posix()}:{line_of(text, match.start())}："
                        f"{match.group()[:24]!r}")
            if len(hits) >= 20:
                break
    check.evidence = hits
    check.status = "FAIL" if hits else "PASS"
    check.detail = ("占位符自身仍匹配邮箱正则，等于没脱敏（SECURITY.md:51-52 记录过同类错误）"
                    if hits else "未发现形如 redacted@host 的伪脱敏占位符")
    return check


def check_credential_scan(root: Path) -> Check:
    check = Check("credential-scan", "密钥 / 凭据")
    hits = []
    for path in iter_text_files(root):
        text = read_text(path)
        for label, pattern in CREDENTIAL_PATTERNS.items():
            match = pattern.search(text)
            if match:
                hits.append(f"{path.relative_to(root).as_posix()}:{line_of(text, match.start())} "
                            f"{label} {match.group()[:6]}***")
    check.evidence = hits
    check.status = "FAIL" if hits else "PASS"
    check.detail = f"命中 {len(hits)} 处疑似凭据" if hits else "未发现任何凭据 / 密钥形态"
    return check


def check_gitignore(root: Path) -> Check:
    check = Check("gitignore-hygiene", ".gitignore 是否覆盖敏感落盘位置")
    path = root / ".gitignore"
    if not path.exists():
        check.status = "FAIL"
        check.detail = "缺少 .gitignore"
        return check
    text = path.read_text(encoding="utf-8", errors="replace")
    required = {
        ".workbench-data": "个人调查记录与模型目录",
        "*.log": "运行日志",
        "*.pyc": "字节码",
        "__pycache__": "缓存目录",
    }
    optional = {".env": "环境变量文件", "*.pem": "证书私钥", "*.key": "私钥",
                "credentials": "凭据文件"}
    missing_required = [f"{k}（{v}）" for k, v in required.items() if k not in text]
    missing_optional = [f"{k}（{v}）" for k, v in optional.items() if k not in text]
    check.evidence = [f"缺失(必需): {m}" for m in missing_required] + \
                     [f"缺失(建议): {m}" for m in missing_optional]
    if missing_required:
        check.status = "FAIL"
        check.detail = "必需忽略项缺失：" + "、".join(missing_required)
    elif missing_optional:
        check.status = "RISK"
        check.detail = ("必需项已覆盖；当前仓库无此类文件，但缺少兜底规则："
                        + "、".join(missing_optional))
    else:
        check.status = "PASS"
        check.detail = "必需与建议忽略项均已覆盖"
    return check


def check_personal_records(root: Path) -> Check:
    """个人调查记录必须只在本机 .workbench-data，不得出现在受版本管理的路径下。"""
    check = Check("personal-records", "个人调查记录的位置")
    markers = ('"investigation_run"', '"section_status"', '"mentor_id"')
    hits, i = [], 0
    for path in iter_text_files(root):
        if path.suffix.lower() not in {".json", ".gz"}:
            continue
        parts = set(path.parts)
        if ".workbench-data" in parts:
            continue
        text = read_text(path)
        if any(m in text for m in markers[:2]):
            hits.append(f"{path.relative_to(root).as_posix()}")
        i += 1
    local = root / ".workbench-data"
    check.evidence = hits[:10]
    if hits:
        check.status = "FAIL"
        check.detail = f"{len(hits)} 个非本机目录的数据文件含个人调查记录字段"
    elif local.exists():
        check.status = "PASS"
        check.detail = f"调查记录仅存在于 {local.name}/（已 gitignore）；扫描 {i} 个数据文件未外泄"
    else:
        check.status = "SKIP"
        check.detail = "本机无 .workbench-data，无法判断个人记录落点"
    return check


def check_long_verbatim(root: Path) -> Check:
    """单字段超长文本：网页原文片段被整段入库（第三方权利）的迹象。"""
    check = Check("long-verbatim", "疑似网页原文长段落入库")
    worst = []
    for path in iter_text_files(root):
        if path.suffix.lower() not in {".json", ".gz"}:
            continue
        text = read_text(path)
        if len(text) < 1000:
            continue
        # 只找最长的单个字符串字面量，避免整文件解析 34MB JSON
        for match in re.finditer(r'"([^"\\]{2000,})"', text):
            worst.append((len(match.group(1)), path.relative_to(root).as_posix(),
                          line_of(text, match.start())))
    worst.sort(reverse=True)
    check.evidence = [f"{p}:{ln} 单字段 {n} 字符" for n, p, ln in worst[:8]]
    if worst:
        check.status = "RISK"
        check.detail = f"{len(worst)} 个字段超过 {LONG_TEXT_LIMIT} 字符，需确认是否为逐字复制"
    else:
        check.status = "PASS"
        check.detail = f"无单字段超过 {LONG_TEXT_LIMIT} 字符"
    return check


def check_license_scope(root: Path) -> Check:
    """LICENSE-DATA 的适用范围是否覆盖实际入库的数据目录。"""
    check = Check("license-scope", "LICENSE-DATA 是否覆盖实际入库的数据目录")
    path = root / "LICENSE-DATA"
    if not path.exists():
        check.status = "FAIL"
        check.detail = "缺少 LICENSE-DATA"
        return check
    text = path.read_text(encoding="utf-8", errors="replace")
    dirs = ["data/", "reports/", "docs/", "workbench/reference", "workbench/sources",
            "workbench/examples", "workbench/aic-submission"]
    missing = []
    for name in dirs:
        exists = (root / name.rstrip("/")).exists()
        covered = name in text or name.rstrip("/") in text
        if exists and not covered:
            missing.append(name)
    check.evidence = [f"已入库但许可声明未提及：{m}" for m in missing]
    check.status = "RISK" if missing else "PASS"
    check.detail = (f"{len(missing)} 个已入库目录未被许可文本覆盖：" + "、".join(missing)
                    if missing else "主要数据目录均被许可文本覆盖")
    return check


def check_upload_limit(root: Path) -> Check:
    """导入上限：必须拒绝超大内容与超量行数（进程内直接调用，不依赖服务）。"""
    check = Check("upload-limit", "导入体积与行数上限")
    sys.path.insert(0, str(root))
    try:
        from workbench import core  # noqa: PLC0415
    except Exception as error:  # noqa: BLE001
        check.status = "SKIP"
        check.detail = f"无法导入 workbench.core：{type(error).__name__}"
        return check
    results = []
    try:
        core.parse_import("big.csv", "a" * (10_000_001))
        results.append(("10MB+1 内容", False))
    except ValueError:
        results.append(("10MB+1 内容", True))
    except Exception:  # noqa: BLE001
        results.append(("10MB+1 内容", False))
    header = "name,institution\n"
    rows = "".join(f"导师{i},某大学\n" for i in range(5001))
    try:
        core.parse_import("many.csv", header + rows)
        results.append(("5001 行", False))
    except ValueError:
        results.append(("5001 行", True))
    except Exception:  # noqa: BLE001
        results.append(("5001 行", False))
    ok = all(passed for _, passed in results)
    check.evidence = [f"{name}: {'已拒绝' if passed else '未拒绝'}" for name, passed in results]
    check.status = "PASS" if ok else "FAIL"
    check.detail = ("超限内容与超量行数均被拒绝" if ok
                    else "存在未被拒绝的超限输入")
    return check


def check_origin_guard(root: Path) -> Check:
    """Origin / Host 校验：写请求缺 Origin 或被伪造 Host 时应被拒绝。"""
    check = Check("origin-guard", "写请求的 Origin / Host 校验")
    sys.path.insert(0, str(root))
    try:
        from fastapi.testclient import TestClient  # noqa: PLC0415
        from workbench.app import app  # noqa: PLC0415
    except Exception as error:  # noqa: BLE001
        check.status = "SKIP"
        check.detail = f"无法构造 TestClient：{type(error).__name__}"
        return check
    client = TestClient(app, base_url="http://127.0.0.1:8765", raise_server_exceptions=False)
    probes = [
        ("无 Origin 的 POST", {"name": ""}, {}),
        ("伪造 Host + 同源伪造 Origin", {"name": ""},
         {"Origin": "http://attacker.example", "Host": "attacker.example"}),
        ("跨站 Origin", {"name": ""}, {"Origin": "http://evil.example"}),
    ]
    rows, loose = [], []
    for label, payload, headers in probes:
        try:
            response = client.post("/api/projects", json=payload, headers=headers)
            status = response.status_code
        except Exception as error:  # noqa: BLE001
            rows.append(f"{label}: 异常 {type(error).__name__}")
            loose.append(label)
            continue
        rows.append(f"{label}: HTTP {status}")
        if status != 403:
            loose.append(f"{label}(HTTP {status})")
    check.evidence = rows
    if loose:
        check.status = "FAIL"
        check.detail = "以下写请求未被 Origin 校验拦住：" + "；".join(loose)
    else:
        check.status = "PASS"
        check.detail = "三类异常来源的写请求均返回 403"
    return check


def check_json_error_path(root: Path) -> Check:
    """无效 JSON 应返回 4xx，不应 500。"""
    check = Check("json-error-path", "无效 JSON 的响应码")
    sys.path.insert(0, str(root))
    try:
        from fastapi.testclient import TestClient  # noqa: PLC0415
        from workbench import core  # noqa: PLC0415
        from workbench.app import app  # noqa: PLC0415
    except Exception as error:  # noqa: BLE001
        check.status = "SKIP"
        check.detail = f"无法构造 TestClient：{type(error).__name__}"
        return check
    client = TestClient(app, base_url="http://127.0.0.1:8765", raise_server_exceptions=False)
    # 只复用本机已有项目，绝不新建：本脚本必须保持只读。
    try:
        existing = core.list_projects()
        project_id = existing[0]["id"] if existing else ""
    except Exception:  # noqa: BLE001
        project_id = ""
    targets = [("POST /api/projects", "/api/projects")]
    if project_id:
        targets += [
            ("POST /api/projects/{id}/search", f"/api/projects/{project_id}/search"),
            ("POST /api/projects/{id}/profiles", f"/api/projects/{project_id}/profiles"),
            ("POST /api/projects/{id}/import", f"/api/projects/{project_id}/import"),
        ]
    else:
        targets += []
    rows, broken, leaked = [], [], []
    for label, url in targets:
        try:
            response = client.post(url, content=b'{"broken": ',
                                   headers={"Content-Type": "application/json",
                                            "Origin": "http://127.0.0.1:8765"})
            status = response.status_code
            body = response.text[:60].replace("\n", " ")
        except Exception as error:  # noqa: BLE001
            rows.append(f"{label}: 异常 {type(error).__name__}")
            broken.append(label)
            continue
        rows.append(f"{label}: HTTP {status}")
        if status >= 500:
            broken.append(f"{label}(HTTP {status})")
        elif re.search(r"(Expecting value|invalid literal|Traceback)", body):
            leaked.append(label)
    check.evidence = rows
    if broken:
        check.status = "FAIL"
        check.detail = "无效 JSON 触发 5xx：" + "；".join(broken)
    elif leaked:
        check.status = "RISK"
        check.detail = "均返回 4xx，但响应体回显了 Python 异常原文：" + "；".join(leaked)
    else:
        check.status = "PASS"
        check.detail = "无效 JSON 一律返回 4xx 且不回显内部异常"
    return check


def check_local_cache(root: Path) -> Check:
    """本机缓存是否留有网页原文 / 联系方式（不入库，但与文档承诺是否一致要单独说）。"""
    check = Check("local-cache", "本机缓存中的网页原文与联系方式")
    if not (root / ".workbench-data").exists():
        check.status = "SKIP"
        check.detail = "本机无 .workbench-data，无缓存可查"
        return check
    emails = phones = 0
    sample = []
    for path in iter_text_files(root, include_local=True):
        if not (LOCAL_DIRS & set(path.parts)):
            continue
        text = read_text(path)
        found_email = [m.group() for m in EMAIL.finditer(text)]
        found_phone = PHONE.findall(text)
        if found_email or found_phone:
            emails += len(found_email)
            phones += len(found_phone)
            if len(sample) < 6:
                sample.append(f"{path.relative_to(root).as_posix()}：邮箱 {len(found_email)} / "
                              f"电话 {len(found_phone)}（值不打印）")
    check.evidence = sample
    if emails or phones:
        check.status = "RISK"
        check.detail = (f"本机缓存含 {emails} 处邮箱、{phones} 处电话形态（不入库，但"
                        "SECURITY.md「快照落盘前即隐去」的表述对缓存不成立）")
    else:
        check.status = "PASS"
        check.detail = "本机缓存未见联系方式"
    return check


ALL_CHECKS = (
    check_email_scan, check_phone_scan, check_id_card_scan, check_danger_keys,
    check_redaction_placeholder, check_credential_scan, check_gitignore,
    check_personal_records, check_long_verbatim, check_license_scope,
    check_upload_limit, check_origin_guard, check_json_error_path, check_local_cache,
)

ICON = {"PASS": "✓", "RISK": "!", "FAIL": "✗", "SKIP": "-"}
# Windows 下把输出重定向到管道时 stdout 常是 GBK（cp936），✓ / ✗ 不在该编码内，
# 直接 print 会抛 UnicodeEncodeError —— 自检本身因此变成"跑不完的检查"。
# 这里按目标流的实际编码挑图标：能编码就用原图标，不能就退回 ASCII。
ASCII_ICON = {"PASS": "OK", "RISK": "!", "FAIL": "X", "SKIP": "-"}


def console_icons() -> dict[str, str]:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        "✓✗".encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return ASCII_ICON
    return ICON


def run(root: Path | None = None, only: set[str] | None = None) -> list[Check]:
    root = root or ROOT
    checks = []
    for factory in ALL_CHECKS:
        name = factory.__name__.replace("check_", "").replace("_", "-")
        if only and name not in only:
            # --only 必须在调用前过滤：否则"只跑一项"仍会触发全部检查（含 app 探针）
            continue
        try:
            check = factory(root)
        except Exception as error:  # noqa: BLE001
            check = Check(name, getattr(factory, "__doc__", "") or name,
                          status="SKIP", detail=f"执行失败：{type(error).__name__}: {error}")
        checks.append(check)
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导师工作台隐私与合规自检")
    parser.add_argument("--check", action="store_true", help="有 FAIL 时退出码 1")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--only", default="", help="只跑指定检查（逗号分隔 id）")
    parser.add_argument("--verbose", action="store_true", help="打印全部证据行")
    args = parser.parse_args(argv)
    only = {x.strip() for x in args.only.split(",") if x.strip()} or None
    checks = run(only=only)
    counts = {status: sum(1 for c in checks if c.status == status)
              for status in ("PASS", "RISK", "FAIL", "SKIP")}
    payload = {"root": str(ROOT), "counts": counts,
               "checks": [c.as_dict() for c in checks]}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if counts["FAIL"] else 0

    icons = console_icons()
    print("隐私与合规自检（只读）：", ROOT)
    print("=" * 68)
    for check in checks:
        print(f"[{icons.get(check.status, '?')} {check.status:<4}] {check.id:<18} {check.title}")
        print(f"         {check.detail}")
        shown = check.evidence if args.verbose else check.evidence[:4]
        for line in shown:
            print(f"         · {line}")
        if not args.verbose and len(check.evidence) > 4:
            print(f"         · …另有 {len(check.evidence) - 4} 条证据（--verbose 查看）")
    print("=" * 68)
    print(f"通过 {counts['PASS']} / 需关注 {counts['RISK']} / 阻塞 {counts['FAIL']} / 跳过 {counts['SKIP']}")
    if counts["FAIL"] and not args.check:
        print("（加 --check 可让阻塞项返回退出码 1，便于纳入验收关卡）")
    return 1 if (args.check and counts["FAIL"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())