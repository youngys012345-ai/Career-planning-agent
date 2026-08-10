"""LLM JSON 抽取：对象包裹数组时不应被截成裸数组。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from wind_agent.llm import extract_json_text  # noqa: E402
from wind_agent.tools import mock_tools  # noqa: E402


def test_extract_prefers_object_wrapping_array():
    raw = json.dumps(
        {
            "conclusions": [
                {"text": "算法岗强调机器学习", "evidence": "依据：第3部分"},
                {"text": "Python 是核心语言", "evidence": "依据：第3部分"},
                {"text": "计科专业更热", "evidence": "依据：第3部分"},
            ]
        },
        ensure_ascii=False,
    )
    extracted = extract_json_text(raw)
    parsed = json.loads(extracted)
    assert isinstance(parsed, dict)
    assert len(parsed["conclusions"]) == 3


def test_extract_still_supports_bare_array():
    raw = '[{"name":"机器学习算法工程师","summary":"建模","source":"generated"}]'
    parsed = json.loads(extract_json_text(raw))
    assert isinstance(parsed, list)
    assert parsed[0]["name"] == "机器学习算法工程师"


def test_extract_strips_fence_and_keeps_object():
    raw = '```json\n{"stages":[{"level":"初级","goal":"打底","action_items":["练Python"]}]}\n```'
    parsed = json.loads(extract_json_text(raw))
    assert isinstance(parsed, dict)
    assert parsed["stages"][0]["level"] == "初级"


def test_stub_conclusions_follow_skill_top_not_data_analysis_boilerplate():
    out = mock_tools._stub_core_conclusions(
        {
            "direction": "算法",
            "skills": [
                {"name": "机器学习 / 算法"},
                {"name": "Python"},
                {"name": "Hadoop / 大数据"},
            ],
            "majors": [{"name": "计算机 / 软件"}, {"name": "统计学 / 应用数学"}],
            "city_supply_stars": [{"city": "北京", "stars": 5}],
        }
    )
    texts = " ".join(c["text"] for c in out["conclusions"])
    assert "算法" in texts
    assert "机器学习" in texts or "Python" in texts
    assert "业务指标与可视化" not in texts


def test_stub_capability_plan_not_bi_centric_for_algorithm():
    out = mock_tools._stub_capability_plan(
        [{"name": "机器学习 / 算法"}, {"name": "Python"}],
        user_text="想做算法工程师",
        direction="算法",
    )
    blob = json.dumps(out, ensure_ascii=False)
    assert "算法" in blob
    assert "留存、转化、运营复盘" not in blob
