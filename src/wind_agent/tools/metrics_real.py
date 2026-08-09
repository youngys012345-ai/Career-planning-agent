"""S1 真指标：详情库词频、分城星级、岗位词典。"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from wind_agent.adapters import job_db

_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config" / "wind_agent"

# 技能分档阈值（相对命中率）
_SKILL_TIERS = [
    (0.55, "高频"),
    (0.30, "中频"),
    (0.0, "低频"),
]
# 专业分档阈值
_MAJOR_TIERS = [
    (0.50, "热招"),
    (0.25, "有招·次热"),
    (0.0, "偶见"),
]

_STAR_LABELS = {
    5: "样本内供给最高档",
    4: "相对高",
    3: "中等",
    2: "相对较低",
    1: "样本内偏低",
}


@lru_cache(maxsize=1)
def _load_json(name: str) -> dict[str, Any]:
    path = _CONFIG_DIR / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def config_dir() -> Path:
    return _CONFIG_DIR


def normalize_city(raw: str, city_list: list[str] | None = None) -> str | None:
    """从脏 city 文本抽取主城名。"""
    text = (raw or "").strip()
    if not text or text in ("全国", "不限", "多地"):
        return None
    cities = city_list or _load_json("city_aliases.json").get("cities") or []
    # 优先匹配较长城名，避免「南京」误匹配
    for city in sorted(cities, key=len, reverse=True):
        if city in text:
            return city
    # 兜底：XX市
    m = re.search(r"([\u4e00-\u9fff]{2,4})市", text)
    if m:
        return m.group(1)
    return None


def _tier(score: float, tiers: list[tuple[float, str]]) -> str:
    for threshold, label in tiers:
        if score >= threshold:
            return label
    return tiers[-1][1]


def _count_lexicon_hits(text: str, entries: list[dict[str, Any]]) -> dict[str, int]:
    """统计词表命中次数（每条 JD 每类最多计 1 次）。"""
    lower = text.lower()
    counts: dict[str, int] = {}
    for entry in entries:
        name = entry["name"]
        aliases = [entry.get("name", "")] + list(entry.get("aliases") or [])
        hit = False
        for alias in aliases:
            a = (alias or "").strip()
            if not a:
                continue
            if a.lower() in lower or a in text:
                hit = True
                break
        if hit:
            counts[name] = counts.get(name, 0) + 1
    return counts


def _to_ranked_items(
    counts: dict[str, int],
    total: int,
    tiers: list[tuple[float, str]],
    *,
    top_n: int = 8,
) -> list[dict[str, Any]]:
    if total <= 0 or not counts:
        return []
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    max_count = ranked[0][1] if ranked else 1
    items: list[dict[str, Any]] = []
    for name, cnt in ranked[:top_n]:
        score = round(cnt / total, 4)
        rel = cnt / max_count if max_count else 0.0
        items.append(
            {
                "name": name,
                "tier": _tier(rel, tiers),
                "score": score,
                "count": cnt,
            }
        )
    return items


def _count_to_stars(counts: dict[str, int], *, top_n: int = 6) -> list[dict[str, Any]]:
    """城计数 → 星级；只取前 top_n，按名次拉开差异（5/4/3/2/1/1）。"""
    if not counts:
        return []
    sorted_items = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:top_n]
    # 固定名次星级，保证城市间差异明显
    rank_stars = [5, 4, 3, 2, 1, 1]
    result: list[dict[str, Any]] = []
    for i, (city, cnt) in enumerate(sorted_items):
        stars = rank_stars[i] if i < len(rank_stars) else 1
        result.append(
            {
                "city": city,
                "stars": stars,
                "label": _STAR_LABELS.get(stars, "中等"),
                "count": cnt,
            }
        )
    return result


def lookup_role_dictionary(direction: str) -> dict[str, Any]:
    """读取方向→子岗词典。"""
    catalog = _load_json("role_dictionary.json")
    subroles = catalog.get(direction) or [
        {"name": f"{direction}相关岗位", "tag": "通用"},
    ]
    return {"direction": direction, "subroles": subroles, "source": "role_dictionary.json"}


def compute_skill_major_freq(
    direction: str,
    *,
    jobs_path: str | Path | None = None,
    exclude_intern: bool = True,
    min_jobs: int = 3,
) -> dict[str, Any]:
    """扫描 JD 描述，计算技能/专业词频分档。"""
    jobs = job_db.filter_jobs(
        direction,
        path=jobs_path,
        exclude_intern=exclude_intern,
    )
    total = len(jobs)
    if total < min_jobs:
        return {
            "direction": direction,
            "skills": [],
            "majors": [],
            "job_count": total,
            "show_block": False,
            "degraded": True,
            "message": f"详情库命中不足（{total}<{min_jobs}），请扩大方向或检查词表",
        }

    skill_entries = _load_json("skill_lexicon.json").get("skills") or []
    major_entries = _load_json("major_lexicon.json").get("categories") or []

    skill_counts: dict[str, int] = {}
    major_counts: dict[str, int] = {}
    for job in jobs:
        text = job_db._searchable_text(job)
        for name, cnt in _count_lexicon_hits(text, skill_entries).items():
            skill_counts[name] = skill_counts.get(name, 0) + cnt
        for name, cnt in _count_lexicon_hits(text, major_entries).items():
            major_counts[name] = major_counts.get(name, 0) + cnt

    return {
        "direction": direction,
        "skills": _to_ranked_items(skill_counts, total, _SKILL_TIERS),
        "majors": _to_ranked_items(major_counts, total, _MAJOR_TIERS, top_n=6),
        "job_count": total,
        "show_block": True,
        "degraded": False,
        "source": "往届公司招聘信息",
    }


def compute_city_supply_stars(
    direction: str,
    *,
    jobs_path: str | Path | None = None,
    exclude_intern: bool = True,
    min_jobs: int = 3,
) -> dict[str, Any]:
    """分城计数 → 1–5 星相对供给。"""
    jobs = job_db.filter_jobs(
        direction,
        path=jobs_path,
        exclude_intern=exclude_intern,
    )
    total = len(jobs)
    if total < min_jobs:
        return {
            "direction": direction,
            "cities": [],
            "job_count": total,
            "show_block": False,
            "degraded": True,
            "message": f"详情库命中不足（{total}<{min_jobs}），无法计算分城星级",
        }

    city_list = _load_json("city_aliases.json").get("cities") or []
    city_counts: dict[str, int] = {}
    for job in jobs:
        city = normalize_city(job.get("city") or "", city_list)
        if city:
            city_counts[city] = city_counts.get(city, 0) + 1

    return {
        "direction": direction,
        "cities": _count_to_stars(city_counts),
        "job_count": total,
        "show_block": bool(city_counts),
        "degraded": not city_counts,
        "source": "往届公司招聘信息",
    }
