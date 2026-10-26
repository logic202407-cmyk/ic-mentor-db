"""接口层防护的回归测试：Host 白名单、Origin 校验、请求体上限、JSON 解析。

这些测试对应三个真实的洞，不是理论风险：

1. 旧中间件只比较 Origin，**不带 Origin 的写请求直接放行**；
2. 旧实现比较的是 `request.url.netloc`，而它由 Host 头决定——攻击者把 Host 与
   Origin 一起伪造成同一个值即可通过，配合 DNS rebinding 能跨站写本机数据；
3. 多处 `await request.json()` 放在 try 之外，无效 JSON 直接冒成 500，并把解析器
   原文回显给调用方（实测 4 处）。

因此这里既测"该拦的拦住"，也测"合法的本机页面不被误伤"。
"""

from __future__ import annotations

import json
import pathlib
import tempfile
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from workbench import core
from workbench.app import ALLOWED_HOSTS, MAX_BODY_BYTES, app

LOCAL_HOST = "127.0.0.1:8765"
LOCAL_ORIGIN = "http://127.0.0.1:8765"


class HostAndOriginTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_write_without_origin_is_rejected(self):
        """写请求不带 Origin 必须 403——旧实现正是在这里放行的。"""
        response = self.client.post("/api/projects", json={"name": "x"},
                                    headers={"host": LOCAL_HOST})
        self.assertEqual(response.status_code, 403)
        self.assertIn("Origin", response.json()["detail"])

    def test_write_with_foreign_origin_is_rejected(self):
        response = self.client.post("/api/projects", json={"name": "x"},
                                    headers={"host": LOCAL_HOST,
                                             "origin": "http://evil.example"})
        self.assertEqual(response.status_code, 403)

    def test_write_with_matching_origin_passes_middleware(self):
        """Origin 与 Host 一致时应进入业务逻辑（这里用缺 name 触发 400 证明已放行）。"""
        response = self.client.post("/api/projects", json={},
                                    headers={"host": LOCAL_HOST, "origin": LOCAL_ORIGIN})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "请填写项目名称")

    def test_spoofed_host_is_rejected(self):
        """Host 与 Origin 一起伪造也必须被拦——这正是旧实现的绕过路径。"""
        response = self.client.post(
            "/api/projects", json={"name": "x"},
            headers={"host": "attacker.example:8765",
                     "origin": "http://attacker.example:8765"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("本机", response.json()["detail"])

    def test_spoofed_host_rejected_on_read_too(self):
        response = self.client.get("/api/health",
                                   headers={"host": "attacker.example:8765"})
        self.assertEqual(response.status_code, 403)

    def test_localhost_host_is_allowed(self):
        response = self.client.get("/api/health", headers={"host": "localhost:8765"})
        self.assertEqual(response.status_code, 200)

    def test_testclient_host_is_allowlisted(self):
        """TestClient 默认 Host 必须在白名单里，否则整套接口测试会被闸门挡死。"""
        self.assertIn("testserver", ALLOWED_HOSTS)
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)


class JsonBodyTests(unittest.TestCase):
    def setUp(self):
        # 这里会真的建项目，必须落在临时目录里，不能往用户的真实资料夹里写测试数据。
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self._tmp.name)
        self._patches = [
            mock.patch.object(core, "DATA_DIR", self.dir),
            mock.patch.object(core, "PROJECTS_DIR", self.dir / "projects"),
        ]
        for patch in self._patches:
            patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        for patch in reversed(self._patches):
            patch.stop()
        self._tmp.cleanup()

    def test_invalid_json_returns_400_not_500(self):
        response = self.client.post(
            "/api/projects", content=b"{not json",
            headers={"content-type": "application/json"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "请求体不是合法 JSON")
        # 不得回显解析器原文（会泄露实现细节）
        self.assertNotIn("Expecting", response.text)

    def test_non_object_json_returns_400(self):
        response = self.client.post(
            "/api/projects", content=b"[1,2,3]",
            headers={"content-type": "application/json"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "请求体应为 JSON 对象")

    def test_invalid_json_on_import_returns_400(self):
        """导入接口原先的 except 写在解析之后，救不了它——现在应稳定 400。"""
        created = self.client.post("/api/projects", json={"name": "测试项目"})
        self.assertEqual(created.status_code, 200)
        project_id = created.json()["id"]
        response = self.client.post(f"/api/projects/{project_id}/import",
                                    content=b"{broken",
                                    headers={"content-type": "application/json"})
        self.assertEqual(response.status_code, 400)


class BodyLimitTests(unittest.TestCase):
    def test_limit_is_a_twelve_megabyte_envelope(self):
        """导入内容上限 10 MB，请求体上限留出 JSON 包装余量。"""
        self.assertEqual(MAX_BODY_BYTES, 12 * 1024 * 1024)

    def test_oversized_content_length_is_rejected(self):
        """在 ASGI 层先拦，避免 `request.json()` 把整个 body 读进内存。"""
        from starlette.requests import Request

        from workbench.app import local_origin

        scope = {
            "type": "http", "method": "POST", "path": "/api/projects",
            "headers": [(b"host", LOCAL_HOST.encode()),
                        (b"origin", LOCAL_ORIGIN.encode()),
                        (b"content-length", str(MAX_BODY_BYTES + 1).encode())],
            "query_string": b"", "scheme": "http", "server": ("127.0.0.1", 8765),
        }

        async def call_next(_request):
            raise AssertionError("超限请求不应进入下游")

        import asyncio
        response = asyncio.run(local_origin(Request(scope), call_next))
        self.assertEqual(response.status_code, 413)

    def test_body_without_content_length_is_capped_too(self):
        """chunked 请求（没有 Content-Length）也必须受同一个上限约束。

        缺陷：中间件只在 `content-length` 头存在且是数字时才拦；
        改用 chunked 传一个更大的 body 就能整个读进内存——上限形同虚设。
        """
        import asyncio

        from fastapi import HTTPException
        from starlette.requests import Request

        from workbench.app import _json_body

        payload = json.dumps({"content": "x" * (MAX_BODY_BYTES + 1024)}).encode("utf-8")
        state = {"left": payload}

        async def receive():
            chunk = state["left"][:65536]
            state["left"] = state["left"][len(chunk):]
            return {"type": "http.request", "body": chunk,
                    "more_body": bool(state["left"])}

        scope = {
            "type": "http", "method": "POST", "path": "/api/projects",
            "headers": [(b"host", LOCAL_HOST.encode()),
                        (b"origin", LOCAL_ORIGIN.encode())],
            "query_string": b"", "scheme": "http", "server": ("127.0.0.1", 8765),
        }

        with self.assertRaises(HTTPException) as caught:
            asyncio.run(_json_body(Request(scope, receive)))
        self.assertEqual(caught.exception.status_code, 413)

    def test_too_large_message_is_derived_from_the_constant(self):
        """413 的文案必须跟着 ``MAX_BODY_BYTES`` 走，不能是另写一遍的字面量。

        缺陷：中间件与 `_read_body` 各写了一遍 `"请求体超过 12 MB"`。两处今天恰好
        都是 12 MB，所以看不出来；一旦把上限改小/改大，提示语仍会说 12 MB，
        变成一个自相矛盾的错误信息，而且没有任何测试会发现。
        """
        from workbench.app import BODY_TOO_LARGE

        mb = MAX_BODY_BYTES // 1024 // 1024
        self.assertIn(str(mb), BODY_TOO_LARGE)
        # 文案里出现的 MB 数字必须只有这一个来源
        import re
        claimed = re.findall(r"(\d+)\s*MB", BODY_TOO_LARGE)
        self.assertEqual(claimed, [str(mb)])

    def test_content_length_alone_is_enforced_inside_read_body(self):
        """即使不经过中间件，`_read_body` 也必须自己拦下超限的 content-length。

        缺陷：`_read_body` 在有 `content-length` 时直接把 `request.body()` 交出去，
        完全依赖中间件先跑。通过 app 访问确实拦得住，但这条路径把安全前提
        押在"调用方一定先过中间件"上，是不必要的耦合。
        """
        import asyncio

        from fastapi import HTTPException
        from starlette.requests import Request

        from workbench.app import _read_body

        async def receive():  # pragma: no cover - 不应被读到
            return {"type": "http.request", "body": b"{}", "more_body": False}

        scope = {
            "type": "http", "method": "POST", "path": "/api/projects",
            "headers": [(b"host", LOCAL_HOST.encode()),
                        (b"origin", LOCAL_ORIGIN.encode()),
                        (b"content-length", str(MAX_BODY_BYTES + 1).encode())],
            "query_string": b"", "scheme": "http", "server": ("127.0.0.1", 8765),
        }

        with self.assertRaises(HTTPException) as caught:
            asyncio.run(_read_body(Request(scope, receive)))
        self.assertEqual(caught.exception.status_code, 413)
        from workbench.app import BODY_TOO_LARGE
        self.assertEqual(caught.exception.detail, BODY_TOO_LARGE)


class SemanticFailureTests(unittest.TestCase):
    """语义模型出错时必须降级成可操作的 503，而不是 500 或回显 Python 原文。

    缺陷：降级分支调用了 `logging.getLogger(...)`，但模块没有 `import logging`，
    于是真实异常被 NameError 顶掉：接口回 500 Internal Server Error，
    服务端也没有留下任何日志。模型不可用时的"稍后重试"提示完全丢失。
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self._tmp.name)
        self._patches = [
            mock.patch.object(core, "DATA_DIR", self.dir),
            mock.patch.object(core, "PROJECTS_DIR", self.dir / "projects"),
        ]
        for patch in self._patches:
            patch.start()
        # 默认 TestClient 会把服务端异常重新抛出，这里要看到真实响应码。
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        for patch in reversed(self._patches):
            patch.stop()
        self._tmp.cleanup()

    def test_semantic_model_failure_degrades_to_503_without_internals(self):
        created = self.client.post("/api/projects", json={"name": "语义降级"})
        self.assertEqual(created.status_code, 200)
        project_id = created.json()["id"]
        with mock.patch("workbench.app.search",
                        side_effect=RuntimeError("C:/models/bge-m3 未找到")):
            response = self.client.post(f"/api/projects/{project_id}/search",
                                        json={"query": "张", "mode": "semantic"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("语义模型", response.json()["detail"])
        # 本机路径、异常类名都不能出现在响应里
        self.assertNotIn("C:/models", response.text)
        self.assertNotIn("NameError", response.text)
        self.assertNotIn("RuntimeError", response.text)


class InvalidProjectIdTests(unittest.TestCase):
    """非法项目 ID 的写请求要与读请求一致：404，而不是 500。

    缺陷：`_project()` 把 ValueError 映射成 404，但 `_mutate_project()` 只认
    FileNotFoundError；同一条坏 ID 走 GET 是 404、走 PATCH 就变成 500。
    """

    def setUp(self) -> None:
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_write_with_malformed_project_id_is_404(self):
        response = self.client.patch("/api/projects/not-a-project-id/profiles/abc",
                                     json={"notes": "x"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "无效的项目 ID")

    def test_read_and_write_agree_on_malformed_project_id(self):
        read = self.client.get("/api/projects/not-a-project-id")
        write = self.client.patch("/api/projects/not-a-project-id/profiles/abc",
                                  json={"notes": "x"})
        self.assertEqual(read.status_code, 404)
        self.assertEqual(write.status_code, read.status_code)


if __name__ == "__main__":
    unittest.main()