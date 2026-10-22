"""homepage_kind 的测试：名录页与本人专属页必须能可靠区分。

这个判据的第一版是错的——用「homepage 等于任一 sources[].url」来判断，结果清华、北大的
正常记录也被判成名录页（因为抓取时把本人主页当成了来源 URL）。这些测试专门钉住正确判据：
**只有等于某个来源模块声明的 ``listing`` 才算名录页**。
"""

from __future__ import annotations

import unittest

from workbench import catalog, homepage_kind


class RosterUrlSetTests(unittest.TestCase):

    def test_roster_urls_is_non_empty(self):
        urls = homepage_kind.roster_urls()
        self.assertGreater(len(urls), 50)
        for url in list(urls)[:5]:
            self.assertFalse(url.endswith("/"), f"应已归一化去掉末尾斜杠：{url}")
            self.assertTrue(url.startswith("http"), url)

    def test_is_roster_url_accepts_trailing_slash(self):
        url = "https://www.cipuc.edu.cn/szdw/yjsds.htm"
        self.assertTrue(homepage_kind.is_roster_url(url))
        self.assertTrue(homepage_kind.is_roster_url(url + "/"))

    def test_unknown_url_is_not_roster(self):
        self.assertFalse(homepage_kind.is_roster_url("https://example.invalid/nobody.htm"))


class KindOfTests(unittest.TestCase):

    def test_empty_is_none(self):
        for value in ("", None, "   "):
            self.assertEqual(homepage_kind.kind_of(value or ""), "none")

    def test_roster_page_is_classified_roster(self):
        # 中国刑事警察学院只公布名录、不公布逐人详情页
        self.assertEqual(
            homepage_kind.kind_of("https://www.cipuc.edu.cn/szdw/yjsds.htm"), "roster")

    def test_detail_page_is_classified_personal(self):
        self.assertEqual(
            homepage_kind.kind_of("https://www.sic.tsinghua.edu.cn/info/1014/1807.htm"),
            "personal")


class RealCatalogTests(unittest.TestCase):
    """用真实目录抽查：两类记录都要出现，否则说明判据退化成一边倒。"""

    @classmethod
    def setUpClass(cls):
        pairs, _by, _raw, _net = catalog.static_catalog()
        cls.kinds = {}
        for p in pairs:
            kind = homepage_kind.kind_of(p.get("homepage") or "")
            cls.kinds[kind] = cls.kinds.get(kind, 0) + 1

    def test_both_classes_are_present(self):
        self.assertGreater(self.kinds.get("roster", 0), 0)
        self.assertGreater(self.kinds.get("personal", 0), 0)

    def test_personal_is_the_majority(self):
        # 名录页回落是少数派（实测约 11.5%）；若这里反转，说明判据又坏了
        roster = self.kinds.get("roster", 0)
        personal = self.kinds.get("personal", 0)
        self.assertLess(roster, personal)

    def test_roster_share_matches_audit_expectation(self):
        roster = self.kinds.get("roster", 0)
        total = sum(self.kinds.values())
        self.assertGreater(total, 1000)
        share = roster / total
        # 审计工具报告 11.5%；给一个宽松但能抓住量级错误的区间
        self.assertGreater(share, 0.02)
        self.assertLess(share, 0.30)


if __name__ == "__main__":
    unittest.main()
