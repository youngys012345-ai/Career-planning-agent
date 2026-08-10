"""Web 静态资源与首页 / 报告模板引用测试。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient

from wind_agent.orchestrator import run_pipeline
from wind_agent.tools.mock_tools import render_html_report
from wind_agent.webapp import create_app


def test_static_assets_served():
    client = TestClient(create_app())
    for path in (
        "/static/css/tokens.css",
        "/static/css/landing.css",
        "/static/css/report.css",
        "/static/css/motion.css",
        "/static/js/landing.js",
        "/static/js/motion.js",
        "/static/js/report-hitl.js",
    ):
        res = client.get(path)
        assert res.status_code == 200, path
        assert len(res.content) > 20


def test_landing_page_uses_static_and_copy():
    client = TestClient(create_app())
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    assert "求职风向标" in html
    assert "市场风向驱动" in html
    assert "面向在校大学生" in html
    assert "推荐方向" in html
    assert "/static/js/landing.js" in html
    assert "/static/css/tokens.css" in html
    assert "/static/css/motion.css" in html
    assert "motion-enter" in html


def test_landing_js_syncs_query_with_recommended_direction():
    """点选推荐方向须同步替换上方 query，避免仍提交默认数据分析文案。"""
    js = (ROOT / "src/wind_agent/static/js/landing.js").read_text(encoding="utf-8")
    assert "PRESET_QUERIES" in js
    assert "applyRecommendedDirection" in js
    assert "setQueryText" in js
    assert "query-flash" in js
    assert 'e.key !== "Enter"' in js
    for key in ("数据分析", "产品经理", "后端开发", "算法"):
        assert key in js
    assert "算法工程师" in js


def test_landing_chips_carry_data_query_and_cache_bust():
    client = TestClient(create_app())
    html = client.get("/").text
    assert 'data-query="' in html
    assert "算法工程师" in html
    assert "/static/js/landing.js?v=" in html
    assert "回车即可生成" in html


def test_report_html_references_static_and_bootstrap():
    pack, _ = run_pipeline(
        direction="数据分析",
        salary_enable=True,
        online_force_empty=False,
        use_real_metrics=False,
        show_m11=True,
        report_id="testhitl02",
    )
    html = render_html_report(pack, report_id="testhitl02")
    assert "/static/css/report.css" in html
    assert "/static/js/motion.js" in html
    assert "/static/js/report-hitl.js" in html
    assert 'id="report-bootstrap"' in html
    assert "testhitl02" in html
    assert "motion-reveal" in html
    assert "这份报告哪里不对" in html
