"""User-confirmed OpenAlex author enrichment for any discipline.

Search results and works are leads only. Matching an author record to a mentor
requires a separate user choice; shared authorship is never labeled mentorship.
"""

from __future__ import annotations

import re
import os
import time
from collections import Counter

import requests

from .core import clean_text, safe_url

API = "https://api.openalex.org"
AUTHOR_ID = re.compile(r"^A\d+$")
TIMEOUT = 15


class OpenAlexUnavailable(Exception):
    """A temporary remote failure that should not change local evidence status."""


def _get(path: str, params: dict) -> dict:
    key = os.environ.get("OPENALEX_API_KEY", "").strip()
    headers = {"User-Agent": "mentor-research-workbench/0.1 (local academic evidence review)"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    for attempt in range(2):
        response = requests.get(API + path, params=params, timeout=TIMEOUT, headers=headers)
        if response.status_code == 429:
            if attempt == 0:
                time.sleep(1)
                continue
            raise OpenAlexUnavailable("OpenAlex 当前限流。可稍后重试，或在启动服务前设置 OPENALEX_API_KEY；本地调查记录未受影响。")
        response.raise_for_status()
        return response.json()
    raise OpenAlexUnavailable("OpenAlex 当前不可用。")


def author_candidates(name: str) -> list[dict]:
    query = re.sub(r"[（(].*[）)]", "", clean_text(name, 80)).strip()
    if not query:
        return []
    data = _get("/authors", {"search": query, "per-page": 10})
    results = []
    for author in data.get("results", []):
        author_id = str(author.get("id", "")).rsplit("/", 1)[-1]
        if not AUTHOR_ID.fullmatch(author_id):
            continue
        affiliations = author.get("last_known_institutions") or []
        if not affiliations:
            affiliations = [item.get("institution", {}) for item in author.get("affiliations", [])[:2]]
        institution_names = [clean_text(item.get("display_name"), 120) for item in affiliations if isinstance(item, dict)]
        results.append({
            "id": author_id, "name": clean_text(author.get("display_name"), 100),
            "institutions": list(dict.fromkeys(filter(None, institution_names)))[:3],
            "works_count": author.get("works_count", 0),
            "url": f"https://openalex.org/{author_id}",
        })
    return results


def works_snapshot(author_id: str) -> dict:
    if not AUTHOR_ID.fullmatch(author_id):
        raise ValueError("无效的 OpenAlex 作者 ID")
    data = _get("/works", {
        "filter": f"author.id:{author_id}", "per-page": 25,
        "sort": "publication_date:desc",
    })
    papers = []
    coauthors: Counter[tuple[str, str]] = Counter()
    for work in data.get("results", []):
        url = safe_url(work.get("doi")) or safe_url(work.get("id"))
        venue = ((work.get("primary_location") or {}).get("source") or {}).get("display_name", "")
        papers.append({
            "title": clean_text(work.get("title"), 350),
            "year": work.get("publication_year"),
            "venue": clean_text(venue, 160),
            "doi": clean_text(work.get("doi"), 160),
            "url": url,
        })
        for authorship in work.get("authorships", []):
            author = authorship.get("author") or {}
            coauthor_id = str(author.get("id", "")).rsplit("/", 1)[-1]
            if not AUTHOR_ID.fullmatch(coauthor_id) or coauthor_id == author_id:
                continue
            coauthors[(coauthor_id, clean_text(author.get("display_name"), 120))] += 1
    return {
        "author_id": author_id,
        "reported_works_count": data.get("meta", {}).get("count"),
        "papers": papers,
        "coauthors": [
            {"id": author, "name": name, "shared_in_sample": count,
             "url": f"https://openalex.org/{author}"}
            for (author, name), count in coauthors.most_common(20)
        ],
        "caveat": "仅展示 OpenAlex 最近最多 25 条作品及其中的共同作者。作者记录可能混入同名者；共同署名不证明师承。",
    }
