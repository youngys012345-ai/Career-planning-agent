"""详情库 JSONL 适配：按方向关键词过滤岗位。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

# 方向 → 检索关键词（标题/薪资行/描述/公司名）
DIRECTION_KEYWORDS: dict[str, list[str]] = {
    "数据分析": [
        "数据分析",
        "数据分析师",
        "商业分析",
        "BI",
        "数据挖掘",
        "数据运营",
        "数据科学家",
        "数据开发",
    ],
    "产品经理": [
        "产品经理",
        "产品专员",
        "产品策划",
        "产品运营",
        "产品助理",
        "PM",
    ],
    "后端开发": [
        "后端",
        "服务端",
        "后台开发",
        "Java开发",
        "Java工程师",
        "Golang",
        "Go开发",
        "Python开发",
        "研发工程师JAVA",
        "研发工程师C/C++",
    ],
}

_DEFAULT_JOBS_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "snapshot" / "campus985_v0" / "jobs.jsonl"
)


def default_jobs_path() -> Path:
    return _DEFAULT_JOBS_PATH


def _searchable_text(job: dict[str, Any]) -> str:
    """拼接可检索字段（校招库 job_title 常为占位）。"""
    parts = [
        job.get("job_title") or "",
        job.get("salary_raw") or "",
        job.get("description") or "",
        job.get("company_name") or "",
        job.get("company_name_raw") or "",
    ]
    return " ".join(str(p) for p in parts if p)


def direction_keywords(direction: str) -> list[str]:
    """返回方向对应关键词；未知方向用方向名本身。"""
    d = (direction or "").strip()
    if d in DIRECTION_KEYWORDS:
        return DIRECTION_KEYWORDS[d]
    return [d] if d else []


def matches_direction(job: dict[str, Any], direction: str) -> bool:
    text = _searchable_text(job).lower()
    keywords = direction_keywords(direction)
    return any(kw.lower() in text for kw in keywords)


def iter_jobs(
    path: Path | str | None = None,
    *,
    direction: str | None = None,
    exclude_intern: bool = True,
) -> Iterator[dict[str, Any]]:
    """逐行读取 JSONL；可按方向过滤并排除实习。"""
    p = Path(path) if path else default_jobs_path()
    if not p.is_file():
        return

    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                job = json.loads(line)
            except json.JSONDecodeError:
                continue
            if exclude_intern and (job.get("job_kind") or "") == "intern":
                continue
            if direction and not matches_direction(job, direction):
                continue
            yield job


def filter_jobs(
    direction: str,
    *,
    path: Path | str | None = None,
    exclude_intern: bool = True,
) -> list[dict[str, Any]]:
    """按方向过滤并返回列表。"""
    return list(
        iter_jobs(path, direction=direction, exclude_intern=exclude_intern)
    )


def count_by_direction(
    direction: str,
    *,
    path: Path | str | None = None,
    exclude_intern: bool = True,
) -> int:
    """统计方向命中条数。"""
    return sum(1 for _ in iter_jobs(path, direction=direction, exclude_intern=exclude_intern))
