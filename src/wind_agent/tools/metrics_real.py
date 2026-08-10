"""S1 真指标：详情库词频、分城星级、岗位词典。"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from wind_agent.adapters import job_db
from wind_agent.tools import supply_db

_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config" / "wind_agent"

# 技能分档阈值（相对命中率 → 产品口径）
_SKILL_TIERS = [
    (0.70, "硬性门槛"),
    (0.35, "高频加分项"),
    (0.0, "基础必备"),
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

# 技能简要说明（市场侧，非人岗匹配）
_SKILL_BLURBS: dict[str, str] = {
    "SQL / 取数": "取数与多表关联是日常分析的基本功；窗口函数与查询优化在面试手撕中常见。",
    "Python": "常用于清洗、批量处理与简易可视化；与 SQL 搭配覆盖多数专题分析。",
    "Excel / 表格": "透视表与常用函数是底线能力，单独不构成竞争力，但缺失会成短板。",
    "BI / 可视化": "看板与报表是常见交付物；Tableau / 帆软 / Power BI 居其一即可。",
    "业务指标 / 分析方法": "能拆解留存、转化、漏斗等指标，是「会取数」与「能分析」的分界。",
    "机器学习 / 算法": "部分岗位加分；校招更常见于算法/数据科学方向，非所有分析岗刚需。",
    "Hadoop / 大数据": "偏数仓与大数据链路；业务分析岗了解分层即可，开发岗要求更高。",
    "Java": "偏工程实现；数据分析主路径非必须，转数据开发时更常见。",
    "数据分析思维": "用数据定义问题、验证假设并给出可执行建议，JD 中高频出现。",
    "沟通协作": "跨部门对齐口径与结论汇报，在业务分析类 JD 中经常作为软性要求。",
    "MySQL / 数据库": "关系库基础与简单建模，支撑取数与口径对齐。",
    "产品需求 / 原型": "偏产品岗；数据产品方向偶见，纯分析岗相对次要。",
}

_TIER_META = {
    "硬性门槛": {"tag_class": "t-hard", "req": "任职要求高频出现"},
    "高频加分项": {"tag_class": "t-plus", "req": "中大厂岗位更常要求"},
    "基础必备": {"tag_class": "t-base", "req": "默认要求，极少单列"},
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


def _skill_blurb(name: str) -> str:
    return _SKILL_BLURBS.get(name) or f"在目标方向 JD 中出现，可作为准备侧重点之一（{name}）。"


def _to_ranked_items(
    counts: dict[str, int],
    total: int,
    tiers: list[tuple[float, str]],
    *,
    top_n: int = 8,
    with_skill_meta: bool = False,
) -> list[dict[str, Any]]:
    if total <= 0 or not counts:
        return []
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    max_count = ranked[0][1] if ranked else 1
    items: list[dict[str, Any]] = []
    for name, cnt in ranked[:top_n]:
        score = round(cnt / total, 4)
        rel = cnt / max_count if max_count else 0.0
        tier = _tier(rel, tiers)
        # 条形图用相对最高项的比例，保证第 1 名拉满、前后差距更直观
        bar_score = round(max(0.08, rel), 4)
        item: dict[str, Any] = {
            "name": name,
            "tier": tier,
            "score": score,
            "bar_score": bar_score,
            "count": cnt,
        }
        if with_skill_meta:
            meta = _TIER_META.get(tier) or _TIER_META["基础必备"]
            item["tag_class"] = meta["tag_class"]
            item["req"] = meta["req"]
            item["blurb"] = _skill_blurb(name)
        items.append(item)
    return items


def _difficulty_from_supply_stars(stars: int) -> tuple[str, str]:
    """由岗位供给星级推算综合难度（供给越多 → 机会越多 → 难度越低，反比）。"""
    if stars >= 4:
        return "较低", "b-easy"
    if stars == 3:
        return "中等", "b-mid"
    return "偏高", "b-hard"


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
        diff_label, diff_class = _difficulty_from_supply_stars(stars)
        result.append(
            {
                "city": city,
                "stars": stars,
                "label": _STAR_LABELS.get(stars, "中等"),
                "count": cnt,
                "difficulty": diff_label,
                "difficulty_class": diff_class,
            }
        )
    return result


def lookup_role_dictionary(direction: str) -> dict[str, Any]:
    """读取方向→子岗词典（方向先模糊归一）。"""
    from wind_agent.adapters.direction_alias import canonical_direction

    catalog = _load_json("role_dictionary.json")
    key = canonical_direction(direction) or (direction or "").strip()
    subroles = catalog.get(key) or catalog.get(direction) or [
        {"name": f"{key or direction}相关岗位", "tag": "通用"},
    ]
    return {"direction": key or direction, "subroles": subroles, "source": "role_dictionary.json"}


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
        "skills": _to_ranked_items(
            skill_counts, total, _SKILL_TIERS, with_skill_meta=True
        ),
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
    supply_path: str | Path | None = None,
    prefer_qcc: bool = True,
    exclude_intern: bool = True,
    min_jobs: int = 3,
) -> dict[str, Any]:
    """分城供给星级：优先企查查快照，缺失时回退校园详情库。"""
    if prefer_qcc:
        qcc = supply_db.lookup_city_supply(direction, path=supply_path)
        if qcc.get("ok") and qcc.get("cities"):
            counts = {
                str(c["city"]): int(c["job_count"])
                for c in qcc["cities"]
                if c.get("city") and int(c.get("job_count") or 0) > 0
            }
            cities = _count_to_stars(counts)
            return {
                "direction": direction,
                "cities": cities,
                "job_count": int(qcc.get("job_count_total") or sum(counts.values())),
                "show_block": bool(cities),
                "degraded": False,
                "source": "企查查招聘地区排行",
                "category_name": qcc.get("category_name"),
                "search_key": qcc.get("search_key"),
                "supply_db": "qcc_city_supply_v0",
            }

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
            "message": f"供给库与详情库均不足以计算分城星级（详情命中 {total}<{min_jobs}）",
            "source": "往届公司招聘信息",
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
        "source": "往届公司招聘信息（供给库未命中，已降级）",
        "fallback": True,
    }
