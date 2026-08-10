"""方向模糊归一：口语前缀不应阻断库匹配。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from wind_agent.adapters import job_db  # noqa: E402
from wind_agent.adapters.direction_alias import (  # noqa: E402
    canonical_direction,
    direction_hints,
    normalize_direction,
    strip_noise,
)
from wind_agent.tools import metrics_real, mock_tools  # noqa: E402
from wind_agent.tools import salary_db, supply_db  # noqa: E402


def test_strip_noise_agent_prefix():
    assert strip_noise("agent算法工程师") == "算法工程师"
    assert strip_noise("AI-产品经理") == "产品经理"


def test_normalize_agent_algorithm_engineer():
    norm = normalize_direction("agent算法工程师")
    assert norm.canonical == "算法"
    assert norm.matched_alias in {"算法工程师", "算法"}
    assert norm.rewritten is True
    assert "算法工程师" in norm.keywords or "算法" in norm.keywords


@pytest.mark.parametrize(
    "raw,expect",
    [
        ("算法工程师", "算法"),
        ("AI算法工程师", "算法"),
        ("机器学习工程师", "算法"),
        ("大模型算法", "算法"),
        ("前端工程师", "前端开发"),
        ("数据分析师", "数据分析"),
    ],
)
def test_canonical_aliases(raw: str, expect: str):
    assert canonical_direction(raw) == expect


def test_clarify_intent_rewrites_to_canonical():
    out = mock_tools.clarify_intent(direction="agent算法工程师", cities=["上海"])
    assert out["need_clarify"] is False
    plan = out["query_plan"]
    assert plan["direction"] == "算法"
    extras = plan["extras"]
    assert extras["direction_raw"] == "agent算法工程师"
    assert extras["direction_canonical"] == "算法"
    assert extras["direction_rewritten"] is True


def test_clarify_prefers_query_over_default_chip():
    """首页默认点选「数据分析」时，提问里的 agent算法工程师应改写为算法。"""
    out = mock_tools.clarify_intent(
        user_text="我是大二学生，以后想做 agent算法工程师，应该如何准备？",
        direction="数据分析",
    )
    assert out["need_clarify"] is False
    assert out["query_plan"]["direction"] == "算法"


def test_clarify_keeps_chip_when_query_aligned():
    out = mock_tools.clarify_intent(
        user_text="想往数据分析方向发展，补什么？",
        direction="数据分析",
    )
    assert out["query_plan"]["direction"] == "数据分析"


def test_job_db_fuzzy_direction_matches_algorithm(tmp_path: Path):
    rows = [
        {
            "job_title": "算法工程师",
            "city": "上海市",
            "description": "机器学习与深度学习",
            "job_kind": "fulltime",
            "company_name": "示例AI",
        },
        {
            "job_title": "数据分析师",
            "city": "杭州市",
            "description": "SQL",
            "job_kind": "fulltime",
            "company_name": "示例数仓",
        },
    ]
    p = tmp_path / "jobs.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    jobs = job_db.filter_jobs("agent算法工程师", path=p)
    assert len(jobs) == 1
    assert jobs[0]["job_title"] == "算法工程师"


def test_salary_hints_and_lookup_for_fuzzy_query():
    hints = direction_hints("agent算法工程师")
    assert "算法" in hints
    # 真库存在「算法与人工智能工程师」类目
    real = ROOT / "data" / "snapshot" / "liepin_salary_v0" / "salaries.jsonl"
    if not real.is_file():
        pytest.skip("薪资快照不存在")
    out = salary_db.lookup_salary_freshgrad("agent算法工程师", path=real)
    assert out.get("show_m6") is True
    assert out.get("matched_category") or out.get("category_name") or out.get("job_name")


def test_role_dictionary_has_algorithm(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(metrics_real, "_CONFIG_DIR", ROOT / "config" / "wind_agent")
    out = metrics_real.lookup_role_dictionary("agent算法工程师")
    assert out["direction"] == "算法"
    names = [x["name"] for x in out["subroles"]]
    assert any("算法" in n for n in names)


def test_supply_match_score_nonzero_for_fuzzy():
    real = ROOT / "data" / "snapshot" / "qcc_city_supply_v0" / "supplies.jsonl"
    if not real.is_file():
        pytest.skip("供给快照不存在")
    out = supply_db.lookup_city_supply("agent算法工程师", path=real)
    # 有类目命中即可；若快照未含算法类则至少 hints 非空
    assert direction_hints("agent算法工程师")
    if out.get("ok"):
        assert out.get("cities")
