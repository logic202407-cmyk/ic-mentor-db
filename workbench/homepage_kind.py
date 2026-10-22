"""判断某条记录的 ``homepage`` 是不是**名录页**（而不是本人的专属页面）。

为什么需要这个
--------------
部分院校只公布名录、不公布逐人详情页（中国刑事警察学院、中国人民警察大学、武汉大学测绘
学科的部分来源等）。这些记录的 ``homepage`` 只能回落到**名录页 URL**。全库实测约 11.5%。

界面上如果一律写「导师主页」，用户会以为点进去是那个人的专属页面——**这是误导**。
所以需要可靠地区分两者。

为什么不能拿 ``sources[].url`` 比
--------------------------------
第一版实现是「homepage 等于任一来源 URL 就算名录页」，**这个判据是错的**：
很多记录的来源 URL 就是本人主页本身（例如抓取个人页作为证据），于是清华、北大的正常记录
也被判成名录页。实测四所全部误判为 True。

正确判据
--------
拿 **来源模块声明的 ``listing``** 做比对——那是"名录页"的定义。一个 URL 只要等于某个模块的
``listing``，它就是名录页；否则不是。这份集合由 :func:`roster_urls` 缓存构造。
"""

from __future__ import annotations

from functools import lru_cache


def _norm(url: str) -> str:
    return (url or "").strip().rstrip("/")


@lru_cache(maxsize=1)
def roster_urls() -> frozenset[str]:
    """所有来源模块声明的名录页 URL（归一化后）。"""
    from .collect_engineering_scale import discover_sources

    urls = set()
    for spec in discover_sources().values():
        listing = _norm(spec.get("listing") or "")
        if listing:
            urls.add(listing)
    return frozenset(urls)


def is_roster_url(url: str) -> bool:
    """该 URL 是否是某个来源模块的名录页（而不是某个人的专属页面）。"""
    return _norm(url) in roster_urls()


def kind_of(url: str) -> str:
    """给界面用的标签：``roster`` / ``personal`` / ``none``。"""
    if not (url or "").strip():
        return "none"
    return "roster" if is_roster_url(url) else "personal"


def clear_cache() -> None:
    roster_urls.cache_clear()
