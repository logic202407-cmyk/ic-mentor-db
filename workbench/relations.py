"""Mentor relationship analysis, layered by evidence strength.

Students care about different relationship questions than a citation graph does:

* **L1 明确师承** — a public statement ("导师为 X") or a supervised-thesis record.
  This is the only layer that is treated as an actual mentorship edge.
* **L2 共同指导/合作** — overlapping time at the same institution with sustained
  co-authorship and first-authored work on both sides. Read as a close working
  relationship, not as proof that one supervised the other.
* **L3 同门** — two people whose stated mentor is the same person. Useful for
  finding peers who came out of the same group.
* **L4 共同署名** — co-authorship only. Explicitly *not* a mentorship signal; it
  is listed so a reader can see the raw evidence rather than infer from it.

Every relation carries its own basis text so a reader can judge it. Common
co-authorship is never promoted to mentorship.
"""

from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NETWORK = ROOT / "data" / "processed" / "network_final.json"

LAYERS = {
    "L1": {
        "key": "mentor",
        "label": "明确师承",
        "student_hint": "有公开表述或学位指导记录支持。可直接用来判断学术出身与师承脉络。",
        "treat_as_mentorship": True,
    },
    "L2": {
        "key": "co_advising",
        "label": "共同指导 / 长期合作",
        "student_hint": "同单位时间段重叠且长期共同署名、双方均有第一作者论文。"
                        "说明两人是紧密合作关系；不等于其中一方指导另一方。",
        "treat_as_mentorship": False,
    },
    "L3": {
        "key": "sibling",
        "label": "同门",
        "student_hint": "两位导师本人出自同一位导师门下。可用来找同门师兄弟所在的课题组。",
        "treat_as_mentorship": False,
    },
    "L4": {
        "key": "coauthor",
        "label": "共同署名",
        "student_hint": "仅表示有共同署名的论文，不构成师承关系。此层仅为原始证据，请勿据此推断指导关系。",
        "treat_as_mentorship": False,
    },
}


def _empty() -> dict:
    return {
        "available": False,
        "reason": "该条目没有公开的关系数据（关系分析目前覆盖历史集成电路专题的导师）。",
        "layers": LAYERS,
        "counts": {code: 0 for code in LAYERS},
        # 与「课题组公开信息观察」用同一套三态词表：无关系数据时四层都是 unknown，
        # 而不是「0 条」——0 条会被读成「查过了，确实没有师承」。
        "layer_states": {code: "unknown" for code in LAYERS},
        "edges": [],
        "peer_names": [],
    }


@lru_cache(maxsize=1)
def _network() -> dict:
    if not NETWORK.exists():
        return {}
    return json.loads(NETWORK.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _index() -> dict[str, dict[str, list[dict]]]:
    """network_key -> {layer_code: [edge, ...]}."""
    net = _network()
    index: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    if not net:
        return {}

    def node(key: str) -> dict:
        return net.get("nodes", {}).get(key, {})

    for row in net.get("advisor", []):
        basis = row.get("basis")
        note = row.get("note") or ""
        # A "stated" basis or an explicit thesis-supervision note is L1; anything
        # else in this file stays L2 rather than being silently upgraded.
        layer = "L1" if basis == "stated" else "L2"
        edge = {
            "from": row.get("s"), "to": row.get("t"),
            "from_name": node(row.get("s", "")).get("name"),
            "to_name": node(row.get("t", "")).get("name"),
            "basis": basis, "note": note, "kind": row.get("kind"),
        }
        index[row["s"]][layer].append(edge)
        index[row["t"]][layer].append({**edge, "from": row.get("t"), "to": row.get("s"),
                                       "from_name": edge["to_name"], "to_name": edge["from_name"]})

    for row in net.get("overlap", []):
        edge = {
            "from": row.get("s"), "to": row.get("t"),
            "from_name": node(row.get("s", "")).get("name"),
            "to_name": node(row.get("t", "")).get("name"),
            "co_papers": row.get("n"), "span": row.get("span"),
            "relation": row.get("type"), "note": row.get("note"),
        }
        index[row["s"]]["L2"].append(edge)
        index[row["t"]]["L2"].append({**edge, "from": row.get("t"), "to": row.get("s"),
                                      "from_name": edge["to_name"], "to_name": edge["from_name"]})

    for row in net.get("sibling", []):
        via = row.get("via")
        edge = {
            "from": row.get("s"), "to": row.get("t"),
            "from_name": node(row.get("s", "")).get("name"),
            "to_name": node(row.get("t", "")).get("name"),
            "via": via, "via_name": node(via or "").get("name"),
        }
        index[row["s"]]["L3"].append(edge)
        index[row["t"]]["L3"].append({**edge, "from": row.get("t"), "to": row.get("s"),
                                      "from_name": edge["to_name"], "to_name": edge["from_name"]})

    for row in net.get("collab", []):
        edge = {
            "from": row.get("s"), "to": row.get("t"),
            "from_name": node(row.get("s", "")).get("name"),
            "to_name": node(row.get("t", "")).get("name"),
            "co_papers": row.get("n"),
        }
        index[row["s"]]["L4"].append(edge)
        index[row["t"]]["L4"].append({**edge, "from": row.get("t"), "to": row.get("s"),
                                      "from_name": edge["to_name"], "to_name": edge["from_name"]})
    return {key: dict(layers) for key, layers in index.items()}


def analyze(network_key: str | None, *, limit_per_layer: int = 20) -> dict:
    """Layered relationship view for one mentor, ordered by evidence strength."""
    if not network_key:
        return _empty()
    layers = _index().get(network_key)
    if not layers:
        return _empty()

    edges = []
    counts = {}
    for code in ("L1", "L2", "L3", "L4"):
        rows = layers.get(code, [])
        counts[code] = len(rows)
        for row in sorted(rows, key=lambda r: (-(r.get("co_papers") or 0), r.get("to_name") or ""))[:limit_per_layer]:
            edges.append({
                "layer": code,
                "label": LAYERS[code]["label"],
                "from": row.get("from"), "to": row.get("to"),
                "from_name": row.get("from_name"), "to_name": row.get("to_name"),
                "co_papers": row.get("co_papers"),
                "span": row.get("span"),
                "via_name": row.get("via_name"),
                "basis": row.get("note") or row.get("relation") or LAYERS[code]["student_hint"],
                "treat_as_mentorship": LAYERS[code]["treat_as_mentorship"],
            })

    net = _network()
    external = [row for row in net.get("external", []) if (row.get("mentor") or "") in {
        (_network().get("nodes", {}).get(k, {}).get("nameEn") or "") for k in (network_key,)}]
    return {
        "available": True,
        "layers": LAYERS,
        "counts": counts,
        # 该条目在关系网内，四层都查过：有记录为 present，无记录为 absent。
        "layer_states": {code: ("present" if counts.get(code) else "absent")
                         for code in ("L1", "L2", "L3", "L4")},
        "edges": edges,
        "mentorship_count": counts.get("L1", 0),
        "peer_names": sorted({e["to_name"] for e in edges
                              if e["layer"] == "L3" and e.get("to_name")}),
        "external_mentors": [
            {"name": row.get("mentor"), "kind": row.get("kind")} for row in external
        ],
        "caveat": "L2/L3/L4 均不是师承关系，只作线索；共同署名不能推断指导关系。",
    }


def summary() -> dict:
    """Whole-network relationship inventory."""
    net = _network()
    if not net:
        return {"available": False}
    meta = net.get("meta", {})
    return {
        "available": True,
        "built_at": meta.get("builtAt"),
        "nodes": meta.get("nodes"),
        "counts": {
            "L1": meta.get("L1", 0),
            "L2": meta.get("L2", 0) + meta.get("overlap", 0),
            "L3": meta.get("siblings", 0),
            "L4": meta.get("L4", 0),
        },
        "external_mentors": meta.get("externalMentors", 0),
        "layers": LAYERS,
        "caveat": "仅 L1 有公开表述或学位指导记录支持；L2–L4 为线索，不是师承。",
    }
