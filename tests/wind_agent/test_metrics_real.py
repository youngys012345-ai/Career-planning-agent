"""S1 真指标单测：词频、星级与门禁。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from wind_agent.adapters import job_db  # noqa: E402
from wind_agent.tools import metrics_real  # noqa: E402


@pytest.fixture()
def jobs_fixture(tmp_path: Path) -> Path:
    """最小 JSONL：3 条数据分析向 JD。"""
    rows = [
        {
            "job_title": "数据分析师",
            "city": "上海市浦东新区",
            "description": "熟练使用 SQL、Python 做业务指标分析，统计学背景优先",
            "job_kind": "fulltime",
            "company_name": "示例科技",
            "salary_raw": "数据分析师",
        },
        {
            "job_title": "商业分析",
            "city": "浙江省杭州市余杭区",
            "description": "Excel 与 BI 可视化，计算机或金融专业",
            "job_kind": "fulltime",
            "company_name": "示例零售",
            "salary_raw": "商业分析",
        },
        {
            "job_title": "数据分析助理",
            "city": "北京市海淀区",
            "description": "SQL 取数，Python pandas，经管类专业亦可",
            "job_kind": "fulltime",
            "company_name": "示例金融",
            "salary_raw": "数据分析",
        },
        {
            "job_title": "实习生",
            "city": "成都市",
            "description": "数据分析实习 SQL",
            "job_kind": "intern",
            "company_name": "应被排除",
            "salary_raw": "实习",
        },
    ]
    p = tmp_path / "jobs.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return p


def test_job_db_filter_excludes_intern(jobs_fixture: Path):
    jobs = job_db.filter_jobs("数据分析", path=jobs_fixture)
    assert len(jobs) == 3
    assert all(j.get("job_kind") != "intern" for j in jobs)


def test_compute_skill_major_freq(jobs_fixture: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(metrics_real, "_CONFIG_DIR", ROOT / "config" / "wind_agent")
    result = metrics_real.compute_skill_major_freq(
        "数据分析",
        jobs_path=jobs_fixture,
        min_jobs=3,
    )
    assert result["show_block"] is True
    assert result["degraded"] is False
    assert result["job_count"] == 3
    skill_names = [s["name"] for s in result["skills"]]
    assert "SQL / 取数" in skill_names
    assert any(s["tier"] == "硬性门槛" for s in result["skills"])
    assert all(s.get("blurb") for s in result["skills"])
    major_names = [m["name"] for m in result["majors"]]
    assert "统计学 / 应用数学" in major_names or "计算机 / 软件" in major_names
    # 条形图相对最高项归一：第 1 名 bar_score = 1.0，且不低于其后名次
    assert result["majors"]
    assert result["majors"][0]["bar_score"] == 1.0
    bars = [m["bar_score"] for m in result["majors"]]
    assert bars == sorted(bars, reverse=True)


def test_compute_city_supply_stars(jobs_fixture: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(metrics_real, "_CONFIG_DIR", ROOT / "config" / "wind_agent")
    # 默认优先企查查种子库（北京领跑，成都不在第一）
    result = metrics_real.compute_city_supply_stars("数据分析")
    assert result["show_block"] is True
    assert "企查查" in (result.get("source") or "")
    assert result["cities"][0]["city"] == "北京"
    assert [c["stars"] for c in result["cities"][:3]] == [5, 4, 3]
    assert len(result["cities"]) <= 6
    top = result["cities"][0]
    assert top["difficulty"] == "较低"
    assert top["difficulty_class"] == "b-easy"
    assert result["cities"][-1]["difficulty"] in ("中等", "偏高")

    # 关闭企查查时回退校园详情库 fixture
    fallback = metrics_real.compute_city_supply_stars(
        "数据分析",
        jobs_path=jobs_fixture,
        min_jobs=3,
        prefer_qcc=False,
    )
    assert fallback["show_block"] is True
    assert "降级" in (fallback.get("source") or "") or "往届" in (fallback.get("source") or "")
    assert {c["city"] for c in fallback["cities"]} >= {"上海", "杭州", "北京"}


def test_gate_when_insufficient_jobs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    p = tmp_path / "tiny.jsonl"
    p.write_text(
        json.dumps(
            {
                "job_title": "数据分析",
                "city": "上海",
                "description": "SQL",
                "job_kind": "fulltime",
                "company_name": "A",
                "salary_raw": "数据分析",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(metrics_real, "_CONFIG_DIR", ROOT / "config" / "wind_agent")
    sm = metrics_real.compute_skill_major_freq("数据分析", jobs_path=p, min_jobs=3)
    # 技能仍看详情库 → 不足则降级；供给默认走企查查种子库 → 仍可出数
    city_qcc = metrics_real.compute_city_supply_stars("数据分析", jobs_path=p, min_jobs=3)
    city_campus = metrics_real.compute_city_supply_stars(
        "数据分析", jobs_path=p, min_jobs=3, prefer_qcc=False
    )
    assert sm["degraded"] is True
    assert sm["show_block"] is False
    assert sm["skills"] == []
    assert city_qcc["show_block"] is True
    assert "企查查" in (city_qcc.get("source") or "")
    assert city_campus["degraded"] is True
    assert city_campus["cities"] == []


def test_lookup_role_dictionary(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(metrics_real, "_CONFIG_DIR", ROOT / "config" / "wind_agent")
    result = metrics_real.lookup_role_dictionary("数据分析")
    assert len(result["subroles"]) >= 3
    assert result["subroles"][0]["name"]


def test_normalize_city():
    assert metrics_real.normalize_city("四川省成都市武侯区") == "成都"
    assert metrics_real.normalize_city("全国") is None
