"""企查查城市岗位供给快照库：读取 qcc_city_supply_v0。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DEFAULT_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "snapshot"
    / "qcc_city_supply_v0"
    / "supplies.jsonl"
)

# 与薪资库对齐的方向匹配 hints
_DIRECTION_HINTS: dict[str, list[str]] = {
    "数据分析": ["数据分析", "数据科学", "商业分析", "数据开发", "大数据"],
    "产品经理": ["产品经理", "产品管理", "产品"],
    "后端开发": ["后端", "Java", "服务端", "软件开发"],
    "算法": ["算法", "人工智能", "机器学习"],
}


@lru_cache(maxsize=4)
def _load_rows(path_str: str) -> list[dict[str, Any]]:
    path = Path(path_str)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def clear_cache() -> None:
    """测试或重新爬取后清空缓存。"""
    _load_rows.cache_clear()


def _match_score(direction: str, row: dict[str, Any]) -> int:
    hints = _DIRECTION_HINTS.get(direction) or [direction]
    blob = " ".join(
        [
            str(row.get("category_name") or ""),
            str(row.get("search_key") or ""),
            " ".join(row.get("aliases") or []),
        ]
    )
    score = 0
    for h in hints:
        if h and h in blob:
            score += 10 if h == direction else 5
    return score


def lookup_city_supply(
    direction: str,
    *,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """按方向匹配供给快照行，返回分城岗位数列表。"""
    db_path = Path(path) if path else _DEFAULT_PATH
    rows = _load_rows(str(db_path))
    if not rows:
        return {
            "ok": False,
            "direction": direction,
            "cities": [],
            "message": f"供给库不存在或为空：{db_path}",
            "source": "qcc_city_supply_v0",
        }

    ranked = sorted(rows, key=lambda r: _match_score(direction, r), reverse=True)
    best = ranked[0] if ranked and _match_score(direction, ranked[0]) > 0 else None
    if best is None:
        return {
            "ok": False,
            "direction": direction,
            "cities": [],
            "message": f"供给库未匹配到方向「{direction}」",
            "source": "qcc_city_supply_v0",
        }

    cities_raw = list(best.get("cities") or [])
    # 过滤无效行，按 job_count 降序
    cities: list[dict[str, Any]] = []
    for c in cities_raw:
        name = str(c.get("city") or "").strip()
        try:
            cnt = int(c.get("job_count") or 0)
        except (TypeError, ValueError):
            cnt = 0
        if not name or cnt <= 0:
            continue
        cities.append(
            {
                "city": name,
                "job_count": cnt,
                "rank": c.get("rank"),
            }
        )
    cities.sort(key=lambda x: (-int(x["job_count"]), x["city"]))
    for i, c in enumerate(cities, start=1):
        c["rank"] = i

    if not cities:
        return {
            "ok": False,
            "direction": direction,
            "cities": [],
            "category_name": best.get("category_name"),
            "search_key": best.get("search_key"),
            "message": "匹配到类目但城市列表为空",
            "source": "qcc_city_supply_v0",
        }

    return {
        "ok": True,
        "direction": direction,
        "cities": cities,
        "category_id": best.get("category_id"),
        "category_name": best.get("category_name"),
        "search_key": best.get("search_key"),
        "crawled_at": best.get("crawled_at"),
        "url": best.get("url"),
        "source": "qcc_city_supply_v0",
        "job_count_total": sum(int(c["job_count"]) for c in cities),
    }


def parse_city_rank_text(text: str) -> list[dict[str, Any]]:
    """从页面/Agent 返回的纯文本中解析「城市 + 岗位数」（供爬虫与单测复用）。"""
    import re

    rows: list[dict[str, Any]] = []
    # 例：北京 12345、上海：1.2万、广州 8,900
    pattern = re.compile(
        r"([\u4e00-\u9fff]{2,8})\s*[:：]?\s*([\d,.]+)\s*([万wW])?",
    )
    for m in pattern.finditer(text or ""):
        city = m.group(1).replace("市", "").strip()
        num_s = m.group(2).replace(",", "")
        try:
            val = float(num_s)
        except ValueError:
            continue
        if m.group(3):
            val *= 10000
        cnt = int(val)
        if cnt <= 0 or city in {"地区", "岗位", "排名", "招聘", "全国"}:
            continue
        rows.append({"city": city, "job_count": cnt})
    # 去重保序，同城取较大值
    merged: dict[str, int] = {}
    order: list[str] = []
    for r in rows:
        c = r["city"]
        if c not in merged:
            order.append(c)
            merged[c] = r["job_count"]
        else:
            merged[c] = max(merged[c], r["job_count"])
    out = [{"city": c, "job_count": merged[c], "rank": i} for i, c in enumerate(order, start=1)]
    out.sort(key=lambda x: (-x["job_count"], x["city"]))
    for i, c in enumerate(out, start=1):
        c["rank"] = i
    return out
