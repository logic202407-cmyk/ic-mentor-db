"""Source-aware mentor discovery using a small open embedding model.

Similarity is relevance to the user's query, never a measure of mentor quality.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np

from .core import DATA_DIR

MODEL_NAME = "BAAI/bge-small-zh-v1.5"
_model = None


def document(profile: dict) -> str:
    parts = [
        f"学科：{profile.get('discipline', '')}",
        f"研究方向：{profile.get('interests', '')}",
        f"简介：{profile.get('summary', '')}",
        f"院系：{profile.get('department', '')}",
    ]
    for source in profile.get("sources", [])[:3]:
        if source.get("claim"):
            parts.append(f"来源线索：{source['claim'][:300]}")
    return "；".join(parts)[:1500]


def keyword_score(query: str, text: str) -> float:
    q = re.sub(r"\s+", "", query.lower())
    t = re.sub(r"\s+", "", text.lower())
    if not q or not t:
        return 0.0
    if q in t:
        return 1.0
    grams = {q[i:i + 2] for i in range(max(1, len(q) - 1))}
    if not grams:
        return float(q in t)
    return sum(g in t for g in grams) / len(grams)


def _embedder():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        cache = DATA_DIR / "models"
        cache.mkdir(parents=True, exist_ok=True)
        _model = TextEmbedding(model_name=MODEL_NAME, cache_dir=str(cache))
    return _model


def _index_path(project_id: str) -> Path:
    directory = DATA_DIR / "indexes"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{project_id}.npz"


def _vectors(project: dict, profiles: list[dict]) -> np.ndarray:
    texts = [document(p) for p in profiles]
    fingerprint = hashlib.sha256(json.dumps(
        [(p["id"], t) for p, t in zip(profiles, texts)], ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    path = _index_path(project["id"])
    if path.exists():
        with np.load(path, allow_pickle=False) as saved:
            if str(saved["fingerprint"]) == fingerprint and str(saved["model"]) == MODEL_NAME:
                return saved["vectors"]
    vectors = np.asarray(list(_embedder().embed(texts)), dtype=np.float32)
    if len(vectors) != len(profiles):
        raise RuntimeError("模型返回的向量数量与导师数量不一致")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    vectors = vectors / np.maximum(norms, 1e-12)
    np.savez_compressed(path, vectors=vectors, fingerprint=fingerprint, model=MODEL_NAME)
    return vectors


def search(project: dict, query: str, mode: str = "semantic", limit: int = 20,
           discipline: str = "", institution: str = "") -> list[dict]:
    query = query.strip()[:300]
    if not query:
        raise ValueError("请输入研究兴趣或检索问题")
    if mode not in {"semantic", "keyword"}:
        raise ValueError("未知的检索方式")
    profiles = [p for p in project["profiles"]
                if (not discipline or discipline.lower() in p["discipline"].lower())
                and (not institution or institution.lower() in p["institution"].lower())]
    if not profiles:
        return []
    if mode == "keyword":
        scores = [keyword_score(query, document(p)) for p in profiles]
    else:
        all_profiles = project["profiles"]
        vectors = _vectors(project, all_profiles)
        qvec = np.asarray(next(iter(_embedder().query_embed(query))), dtype=np.float32)
        qvec /= max(float(np.linalg.norm(qvec)), 1e-12)
        all_scores = vectors @ qvec
        id_to_score = {p["id"]: float(score) for p, score in zip(all_profiles, all_scores)}
        scores = [id_to_score[p["id"]] for p in profiles]
    order = sorted(range(len(profiles)), key=lambda i: (-scores[i], profiles[i]["name"]))
    return [{
        "profile": profiles[i],
        "similarity": round(float(scores[i]), 4),
        "mode": mode,
        "evidence_count": len(profiles[i].get("sources", [])),
    } for i in order[:max(1, min(int(limit), 100))] if scores[i] > 0]
