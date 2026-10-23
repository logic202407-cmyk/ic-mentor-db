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

import unittest

from fastapi.testclient import TestClient

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
        self.client = TestClient(app)

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


if __name__ == "__main__":
    unittest.main()