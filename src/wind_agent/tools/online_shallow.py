"""在线多站浅采：优先智联公开搜索页；失败可降级为空（由编排决定是否展示）。"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote


def _parse_zhilian_state(html: str) -> list[dict[str, Any]]:
    m = re.search(r"__INITIAL_STATE__\s*=\s*(\{.+?\})\s*;?\s*</script>", html, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    rows = data.get("positionList") or []
    items: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        company = (row.get("companyName") or row.get("companyShortName") or "").strip()
        title = (row.get("positionName") or row.get("name") or "").strip()
        city = (row.get("cityName") or row.get("workCity") or "").strip()
        desc = (row.get("jobSummary") or row.get("positionHighlight") or "").strip()
        if isinstance(desc, list):
            desc = "；".join(str(x) for x in desc if x)
        if not company or not title:
            continue
        items.append(
            {
                "source": "zhilian",
                "company": company,
                "job_title": title,
                "city": city,
                "description": desc[:500] if desc else "",
            }
        )
    return items


def _fetch_zhilian(direction: str, *, limit: int = 12) -> list[dict[str, Any]]:
    try:
        from curl_cffi import requests
    except ImportError:
        return []

    url = f"https://sou.zhaopin.com/?kw={quote(direction)}&p=1"
    try:
        resp = requests.get(url, impersonate="chrome124", timeout=18)
        if resp.status_code != 200:
            return []
        html = resp.content.decode("utf-8", "replace")
    except Exception:
        return []
    return _parse_zhilian_state(html)[:limit]


def online_job_search(
    direction: str,
    cities: list[str] | None = None,
    force_empty: bool = False,
) -> dict[str, Any]:
    """在线浅采：智联列表第 1 页；合格校验由 validate_online_jobs 负责。"""
    _ = cities  # 城市筛选用作后续扩展；当前以全国关键词搜索为主
    if force_empty:
        return {"items": [], "sources": [], "mode": "empty"}

    items = _fetch_zhilian(direction)
    if items:
        return {
            "items": items,
            "sources": ["zhilian"],
            "mode": "live",
            "note": "在线浅采 · 智联公开搜索第 1 页",
        }

    # 实时失败时返回空，模块门禁隐藏（不回退离线库冒充在线）
    return {
        "items": [],
        "sources": [],
        "mode": "failed",
        "note": "在线浅采失败或被拦截",
    }
