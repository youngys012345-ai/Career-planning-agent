"""岗位平均薪资库：读取 liepin_salary_v0，取「1年以下」档。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DEFAULT_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "snapshot"
    / "liepin_salary_v0"
    / "salaries.jsonl"
)

# 方向 → 薪资库类目名关键字（用于匹配 category_name / aliases）
_DIRECTION_HINTS: dict[str, list[str]] = {
    "数据分析": ["数据分析", "数据科学", "商业分析", "数据开发"],
    "产品经理": ["产品经理", "产品"],
    "后端开发": ["后端", "Java", "服务端", "软件开发"],
    "算法": ["算法", "人工智能", "机器学习"],
}


@lru_cache(maxsize=1)
def _load_rows(path_str: str) -> list[dict[str, Any]]:
    path = Path(path_str)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _match_score(direction: str, row: dict[str, Any]) -> int:
    hints = _DIRECTION_HINTS.get(direction) or [direction]
    blob = " ".join(
        [
            str(row.get("category_name") or ""),
            str(row.get("job_name") or ""),
            " ".join(row.get("aliases") or []),
        ]
    )
    score = 0
    for h in hints:
        if h and h in blob:
            score += 10 if h == direction else 5
    return score


def _yuan_to_k(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x > 200:  # 元
        return round(x / 1000.0, 2)
    return round(x, 2)


def lookup_salary_freshgrad(
    direction: str,
    enable: bool = True,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """查薪资库：优先「1年以下」全国均薪，分城用 city_salary 按年限比缩放。"""
    if not enable:
        return {"show_m6": False, "salary_by_city": None}

    db_path = Path(path) if path else _DEFAULT_PATH
    rows = _load_rows(str(db_path))
    if not rows:
        return {
            "show_m6": False,
            "salary_by_city": None,
            "message": f"薪资库不存在或为空：{db_path}",
        }

    ranked = sorted(rows, key=lambda r: _match_score(direction, r), reverse=True)
    best = ranked[0] if ranked and _match_score(direction, ranked[0]) > 0 else None
    if best is None:
        return {
            "show_m6": False,
            "salary_by_city": None,
            "message": f"薪资库未匹配到方向：{direction}",
        }

    year_map = best.get("year_salary") or {}
    # 兼容不同编码/写法
    lt1 = None
    for key in ("1年以下", "1年以下 ", "应届生", "应届"):
        if key in year_map:
            lt1 = year_map[key]
            break
    if lt1 is None:
        # 取最短年限档
        for k, v in year_map.items():
            if "1年" in str(k) and "以下" in str(k):
                lt1 = v
                break
    all_avg = year_map.get("全部年限")
    lt1_k = _yuan_to_k(lt1)
    all_k = _yuan_to_k(all_avg)
    scale = (lt1_k / all_k) if (lt1_k and all_k and all_k > 0) else 1.0

    city_salary = best.get("city_salary") or {}
    dist_raw = best.get("salary_distribution") or {}
    distribution = [
        {"bucket": str(k), "pct": float(v) / 100.0 if float(v) > 1 else float(v)}
        for k, v in dist_raw.items()
    ]

    cities_out: list[dict[str, Any]] = []
    for city, avg in city_salary.items():
        mean_k = _yuan_to_k(avg)
        if mean_k is None:
            continue
        adj = round(mean_k * scale, 2)
        cities_out.append(
            {
                "city": city,
                "mean_k": adj,
                "p25": round(adj * 0.85, 2),
                "p50": adj,
                "p75": round(adj * 1.15, 2),
                "distribution": distribution,
            }
        )
    cities_out.sort(key=lambda x: -x["mean_k"])

    if not cities_out and lt1_k:
        cities_out = [
            {
                "city": "全国",
                "mean_k": lt1_k,
                "p25": round(lt1_k * 0.85, 2),
                "p50": lt1_k,
                "p75": round(lt1_k * 1.15, 2),
                "distribution": distribution,
            }
        ]

    return {
        "show_m6": bool(cities_out),
        "work_year": "lt_1y",
        "category_name": best.get("category_name"),
        "national_lt1y_k": lt1_k,
        "sample_count": best.get("sample_count"),
        "salary_by_city": cities_out,
        "source": "liepin_salary_v0",
    }
