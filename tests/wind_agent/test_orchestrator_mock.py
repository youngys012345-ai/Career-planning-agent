"""S0 编排与门禁单测。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from wind_agent.orchestrator import run_pipeline


def test_mock_pipeline_shows_salary_and_latest():
    pack, html = run_pipeline(
        direction="数据分析",
        salary_enable=True,
        online_force_empty=False,
        use_real_metrics=False,
        show_m11=True,
        report_id="testhitl01",
    )
    assert pack.flags["show_m6"] is True
    assert pack.flags["show_m9"] is True
    assert pack.online["qualified_count"] >= 3
    assert "预期薪资" in html
    assert "求职风向" in html
    assert "这份报告哪里不对" in html
    assert "平均" in html
    assert "sal-box" in html
    assert "P25" not in html
    assert "P75" not in html
    assert "大中小型公司" in html
    assert "40k" in html  # 横轴等距刻度含 40k，与线性定位一致
    assert "在线可见公司" not in html
    assert "岗位标题簇" not in html
    assert "最新进展" not in html
    assert "就业难度" not in html
    assert "Evidence Pack" not in html
    # 箱线图定位在 0～50k 线性轴上（例：11.5k → 23%）
    assert any((c.get("box_width_pct") or 0) > 0 for c in pack.metrics["salary_by_city"])
    for c in pack.metrics["salary_by_city"]:
        mean = float(c.get("mean_k") or 0)
        axis = float(c.get("axis_max_k") or 50)
        expected = round(max(0.0, min(100.0, mean / axis * 100.0)), 2)
        assert c.get("mean_left_pct") == expected
    assert pack.generated["latest"].get("analysis")
    assert pack.generated["latest"].get("source_platform")


def test_hide_salary_and_latest_when_gated():
    pack, html = run_pipeline(
        direction="数据分析",
        salary_enable=False,
        online_force_empty=True,
        use_real_metrics=False,
    )
    assert pack.flags["show_m6"] is False
    assert pack.flags["show_m9"] is False
    assert "预期薪资" not in html
    # mock 路径下在线不足时不展示求职风向块
    assert pack.generated["latest"].get("show_m9") is False
    assert "核心能力与专业" in html


def test_user_query_shown_in_hero():
    q = "我现在是大二统计专业学生，以后想找数据分析岗位工作，我应该如何准备。"
    pack, html = run_pipeline(
        user_text=q,
        direction="数据分析",
        use_real_metrics=False,
        online_force_empty=True,
        salary_enable=False,
    )
    assert pack.query_plan.user_query == q
    assert q in html
    assert "意愿方向驱动" not in html
