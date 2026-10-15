"""Small, reproducible retrieval sanity check on the source-linked pilot.

Queries and expected profiles were written from the cited public pages. This is
an engineering smoke check, not an unbiased benchmark or user-effect study.
"""

import json
import uuid
from pathlib import Path

from workbench.core import normalize_profile
from workbench.search import search

ROOT = Path(__file__).resolve().parent
QUERIES = [
    ("利用图像识别理解复杂场景", "张涛"),
    ("中国古代政治制度和边疆文献", "顾涛"),
    ("平台数据权益与开源项目法律", "张平"),
    ("用算法分析基因功能和生命系统", "张一婧"),
    ("驾驶场景下的人类注意与交互", "张学民"),
    ("历史街区改造与遗产空间", "黄鹤"),
    ("棉花育种性状研究", "李威"),
    ("病原体跨物种传播与防控", "粟硕"),
]


def main() -> None:
    data = json.loads((ROOT / "examples" / "official_source_pilot.json").read_text(encoding="utf-8"))
    project = {"id": uuid.uuid4().hex, "profiles": [normalize_profile(row) for row in data["profiles"]]}
    print("试点档案：", len(project["profiles"]), "条；查询：", len(QUERIES), "条")
    for mode in ("keyword", "semantic"):
        top1 = 0
        top3 = 0
        for query, expected in QUERIES:
            results = search(project, query, mode=mode, limit=3)
            names = [item["profile"]["name"] for item in results]
            top1 += bool(names and names[0] == expected)
            top3 += expected in names
            print(f"{mode:8} {query} -> {','.join(names)} | 目标：{expected}")
        print(f"{mode} Top-1 {top1}/{len(QUERIES)}, Top-3 {top3}/{len(QUERIES)}")


if __name__ == "__main__":
    main()
