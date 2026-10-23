"""「课题组公开信息观察」的测试。

这一组的由来
------------
改版前 ``workbench/student_score.py`` 输出一个 0–100 的「读研体验参考分」，
并且在没有论文记录时把「组内活跃度」直接算成 **0 分** —— 把"我们没抓到"当成
"这个组不活跃"。学生看到 0 会当成负面判断。同时综合分会诱导读者跨导师排序，
而不同导师的可核实论文数从 0 到 300 不等，排序没有可比性。

所以这些测试钉三件事：

1. 三态严格：``unknown``（无公开证据）**绝不能**变成 0 或任何数字；
   ``absent``（有证据且确为 0）才允许出现 0。
2. 没有综合分：``score`` / ``confidence`` / ``weights`` 只能存在且为 ``None``，
   不得参与任何排序。
3. 结构齐备：四个维度每个都带事实、原始数值、样本量、取数依据与边界说明。
"""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from workbench import catalog, student_score
from workbench.app import app

NUMERIC_DIMENSIONS = ("authorship", "group_size", "recent_output")
ALL_DIMENSIONS = student_score.DIMENSIONS


def _samples() -> dict[str, str]:
    """挑几条真实记录，覆盖「数据完整 / 无论文 / 缺主页」三种情况。"""
    index = student_score.ranked_index()
    complete = no_paper = no_homepage = stale_output = ""
    for key, row in index.items():
        papers = int(row.get("n_ic_papers") or 0)
        if complete and no_paper and no_homepage and stale_output:
            break
        if not complete and papers >= 20 and isinstance(row.get("student_led_ratio"), (int, float)):
            complete = key
        if not no_paper and papers == 0:
            no_paper = key
        if not no_homepage and papers >= 5 and not (row.get("homepage") or "").strip():
            no_homepage = key
        # 注意不能写 `or -1`：recent3 为 0 时会被替换成 -1，正好漏掉要找的那类记录。
        if not stale_output and papers >= 5 and row.get("recent3") == 0:
            stale_output = key
    return {"complete": complete, "no_paper": no_paper,
            "no_homepage": no_homepage, "stale_output": stale_output}


#: 一个真实的「名录页」URL：中国刑事警察学院只公布名录、不公布逐人详情页。
ROSTER_URL = "https://www.cipuc.edu.cn/szdw/yjsds.htm"


class ThreeStateTests(unittest.TestCase):
    """present / absent / unknown 三态，unknown 不得显示成 0。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.samples = _samples()
        for name, key in cls.samples.items():
            assert key, f"样本 {name} 未找到：数据结构可能已变化"

    def test_unknown_mentor_has_no_numbers(self) -> None:
        result = student_score.compute("不存在的学校|不存在的姓名")
        self.assertFalse(result["available"])
        self.assertTrue(result["reason"])
        for key in ALL_DIMENSIONS:
            dimension = result["dimensions"][key]
            self.assertEqual(dimension["state"], "unknown", key)
            self.assertFalse(dimension["available"], key)
            self.assertIsNone(dimension["value"], key)
            self.assertNotIn("0", dimension["display"],
                             f"{key} 无公开证据时不得显示 0，实际 {dimension['display']!r}")

    def test_missing_paper_data_is_unknown_not_zero(self) -> None:
        """原实现的核心 bug：没有论文记录时组内活跃度算 0 分。"""
        result = student_score.compute(self.samples["no_paper"])
        for key in NUMERIC_DIMENSIONS:
            dimension = result["dimensions"][key]
            self.assertEqual(dimension["state"], "unknown",
                             f"{key} 无论文数据时必须是 unknown，实际 {dimension['state']}")
            self.assertIsNone(dimension["value"])
            self.assertNotEqual(dimension["display"].strip(), "0", key)
            self.assertNotEqual(dimension["display"].strip(), "0%", key)

    def test_evidence_backed_zero_is_absent(self) -> None:
        """有论文记录但近三年为 0：这次是「有证据的 0」，必须是 absent 而非 unknown。"""
        row = student_score.ranked_index()[self.samples["stale_output"]]
        self.assertGreater(int(row.get("n_ic_papers") or 0), 0)
        self.assertEqual(int(row.get("recent3") or 0), 0)
        dimension = student_score.compute(self.samples["stale_output"])["dimensions"]["recent_output"]
        self.assertEqual(dimension["state"], "absent")
        self.assertEqual(dimension["value"], 0)
        self.assertIn("0", dimension["display"])
        # 边界说明必须写清「0 也可能是我们没检索到」，避免被读成负面评价
        self.assertIn("检索未覆盖", dimension["fact"] + dimension["boundary"])

    def test_authorship_hidden_below_threshold(self) -> None:
        """可核实论文少于 3 篇时不展示占比 —— 0/2 与 0/200 不是一回事。"""
        index = student_score.ranked_index()
        thin = next((key for key, row in index.items()
                     if 0 < int(row.get("n_ic_papers") or 0) < student_score.MIN_PAPERS_FOR_AUTHORSHIP),
                    None)
        if thin is None:
            self.skipTest("没有样本量在门槛以下的记录")
        dimension = student_score.compute(thin)["dimensions"]["authorship"]
        self.assertEqual(dimension["state"], "unknown")
        self.assertIsNone(dimension["value"])
        self.assertIn(str(student_score.MIN_PAPERS_FOR_AUTHORSHIP), dimension["fact"])

    def test_no_unknown_dimension_ever_renders_a_number(self) -> None:
        """全库扫描：状态为 unknown 的维度一律不得带数字。"""
        for key in student_score.ranked_index():
            result = student_score.compute(key)
            for name, dimension in result["dimensions"].items():
                if dimension["state"] != "unknown":
                    continue
                self.assertIsNone(dimension["value"], f"{key} {name}")
                self.assertFalse(dimension["available"], f"{key} {name}")
                self.assertNotRegex(
                    dimension["display"], r"^\s*\d",
                    f"{key} 的 {name} 无公开证据却显示了数字：{dimension['display']!r}")


class NoCompositeScoreTests(unittest.TestCase):
    """不再有综合分，也不再有跨导师排序。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.samples = _samples()
        cls.result = student_score.compute(cls.samples["complete"])

    def test_score_fields_are_retired_but_kept_for_compatibility(self) -> None:
        for field in ("score", "confidence", "weights"):
            self.assertIn(field, self.result, f"兼容字段 {field} 应保留键名")
            self.assertIsNone(self.result[field], f"{field} 不得再有数值")

    def test_view_is_an_observation_not_a_score(self) -> None:
        self.assertEqual(self.result["view"], "group_public_observations")
        self.assertIn("观察", self.result["title"])
        self.assertNotIn("分", self.result["title"])

    def test_no_ranking_or_grade_fields(self) -> None:
        forbidden = {"rank", "ranking", "percentile", "grade", "level", "overall", "total"}
        self.assertEqual(forbidden & set(self.result), set(),
                         "观察视图不得携带排名/等级字段")

    def test_deprecated_note_explains_the_retired_fields(self) -> None:
        self.assertEqual(set(self.result["deprecated_fields"]), {"score", "confidence", "weights"})
        self.assertIn("null", self.result["deprecated_note"])

    def test_not_measured_lists_what_it_cannot_judge(self) -> None:
        joined = " ".join(self.result["not_measured"])
        for topic in ("学术水平", "氛围", "补助", "报考建议"):
            self.assertIn(topic, joined)


class DimensionCoverageTests(unittest.TestCase):
    """四维度齐备，且每个维度都带事实 / 数值 / 样本 / 依据 / 边界。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.samples = _samples()
        cls.result = student_score.compute(cls.samples["complete"])

    def test_four_dimensions_are_always_present(self) -> None:
        self.assertEqual(tuple(self.result["order"]), ALL_DIMENSIONS)
        self.assertEqual(set(self.result["dimensions"]), set(ALL_DIMENSIONS))
        # 没有数据的条目也要给出四个维度，不能只留空
        blank = student_score.compute(None)
        self.assertEqual(set(blank["dimensions"]), set(ALL_DIMENSIONS))

    def test_every_dimension_carries_evidence_fields(self) -> None:
        required = {"label", "state", "available", "value", "display", "sample",
                    "sample_label", "fact", "basis", "boundary"}
        for name, dimension in self.result["dimensions"].items():
            self.assertTrue(required <= set(dimension), f"{name} 缺少字段：{required - set(dimension)}")
            self.assertIn(dimension["state"], {"present", "absent", "unknown"})
            self.assertTrue(dimension["fact"].strip(), f"{name} 缺事实描述")
            self.assertTrue(dimension["basis"].strip(), f"{name} 缺取数依据")
            self.assertTrue(dimension["boundary"].strip(), f"{name} 缺边界说明")
            self.assertIsInstance(dimension["label"], str)
            self.assertIn(dimension["label"], self.result["labels"].values())

    def test_numeric_dimensions_expose_raw_value_and_sample(self) -> None:
        for name in NUMERIC_DIMENSIONS:
            dimension = self.result["dimensions"][name]
            self.assertIsInstance(dimension["value"], (int, float), name)
            self.assertIsNotNone(dimension["sample"], name)
            self.assertIn("篇", dimension["sample_label"], name)

    def test_group_size_is_labelled_as_a_cumulative_count(self) -> None:
        """人数必须写成「累计」，不能被读成「现在带多少学生」。

        ``n_students_est`` 是跨年份累计的不同一作姓名数（黄如 305 篇 → 165 个姓名）。
        写成「组内学生规模」或「下限」都会把人数误解释成培养资源。
        """
        dimension = self.result["dimensions"]["group_size"]
        self.assertIn("累计", dimension["display"])
        self.assertIn("非在读", dimension["display"])
        self.assertNotIn("下限", dimension["display"])
        self.assertNotIn("下限", dimension["label"])
        self.assertIn("累计", dimension["label"])
        self.assertIn("不是在读学生数", dimension["fact"])
        self.assertIn("不可用于横向比较", dimension["boundary"])
        self.assertNotIn("下限", dimension["boundary"])

    def test_transparency_is_a_three_item_checklist_without_a_score(self) -> None:
        dimension = self.result["dimensions"]["transparency"]
        self.assertNotIn("facts", self.result["dimensions"]["authorship"],
                         "只有信息公开度是事实清单")
        self.assertEqual(len(dimension["facts"]), 3)
        self.assertIsNone(dimension["value"], "信息公开度不打分")
        keys = {fact["key"] for fact in dimension["facts"]}
        self.assertEqual(keys, {"homepage", "research_direction", "phd_advisor"})
        for fact in dimension["facts"]:
            self.assertIn(fact["state"], {"present", "absent", "unknown"})

    def test_roster_page_is_not_reported_as_a_personal_homepage(self) -> None:
        """名录页不能被说成「本人专属主页」——那是误导。

        这里直接测判定函数：历史 IC 语料里没有名录页回落的记录，靠真实数据抽样
        覆盖不到这条分支，只能喂一个真实的名录页 URL。
        """
        dimension = student_score._transparency(
            {"research_keywords": ["测试方向"], "is_phd_advisor": True}, ROSTER_URL)
        homepage = next(fact for fact in dimension["facts"] if fact["key"] == "homepage")
        self.assertEqual(homepage["state"], "absent")
        self.assertIn("名录页", homepage["value"])

    def test_personal_page_is_reported_as_present(self) -> None:
        dimension = student_score._transparency(
            {"research_keywords": ["测试方向"], "is_phd_advisor": True},
            "https://www.sic.tsinghua.edu.cn/info/1014/1807.htm")
        homepage = next(fact for fact in dimension["facts"] if fact["key"] == "homepage")
        self.assertEqual(homepage["state"], "present")

    def test_missing_homepage_is_unknown_not_absent(self) -> None:
        dimension = student_score.compute(self.samples["no_homepage"])["dimensions"]["transparency"]
        homepage = next(fact for fact in dimension["facts"] if fact["key"] == "homepage")
        self.assertEqual(homepage["state"], "unknown",
                         "没收录链接不等于导师没有主页")

    def test_evidence_counts_match_dimension_states(self) -> None:
        counts = self.result["evidence_counts"]
        self.assertEqual(sum(counts.values()), len(ALL_DIMENSIONS))
        actual = {state: 0 for state in ("present", "absent", "unknown")}
        for dimension in self.result["dimensions"].values():
            actual[dimension["state"]] += 1
        self.assertEqual(counts, actual)


class ApiCompatibilityTests(unittest.TestCase):
    """``/api/catalog/mentor/{id}`` 继续返回 ``student_score`` 键，但内容已是观察视图。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        pairs, _by, _raw, _net = catalog.static_catalog()
        cls.mentor_id = pairs[0]["id"]

    def test_student_score_key_is_kept(self) -> None:
        response = self.client.get(f"/api/catalog/mentor/{self.mentor_id}")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("student_score", body, "键名必须保留，避免破坏前端与既有测试")

    def test_payload_is_the_observation_view(self) -> None:
        body = self.client.get(f"/api/catalog/mentor/{self.mentor_id}").json()
        observation = body["student_score"]
        self.assertEqual(observation["view"], "group_public_observations")
        self.assertEqual(set(observation["dimensions"]), set(ALL_DIMENSIONS))
        for field in ("score", "confidence", "weights"):
            self.assertIsNone(observation[field])

    def test_homepage_is_consistent_with_the_dossier_header(self) -> None:
        """观察里的主页判定要用界面实际展示的那个链接，不能各说一套。"""
        body = self.client.get(f"/api/catalog/mentor/{self.mentor_id}").json()
        homepage_fact = next(fact for fact in body["student_score"]["dimensions"]["transparency"]["facts"]
                             if fact["key"] == "homepage")
        kind = body["homepage_kind"]
        expected = {"personal": "present", "roster": "absent", "none": "unknown"}[kind]
        self.assertEqual(homepage_fact["state"], expected)

    def test_unknown_mentor_is_404_not_an_empty_score(self) -> None:
        self.assertEqual(
            self.client.get("/api/catalog/mentor/legacy-00000000000000000000").status_code, 404)


if __name__ == "__main__":
    unittest.main()