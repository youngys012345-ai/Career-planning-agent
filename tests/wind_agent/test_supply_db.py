"""企查查城市供给库单测。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from wind_agent.tools import metrics_real, supply_db


@pytest.fixture()
def supply_fixture(tmp_path: Path) -> Path:
    p = tmp_path / "supplies.jsonl"
    rows = [
        {
            "category_id": "cat_11",
            "category_name": "数据分析与大数据工程",
            "aliases": ["数据分析师"],
            "search_key": "数据分析",
            "source": "qcc_recruit",
            "cities": [
                {"city": "北京", "job_count": 10000, "rank": 1},
                {"city": "上海", "job_count": 8000, "rank": 2},
                {"city": "深圳", "job_count": 6000, "rank": 3},
                {"city": "成都", "job_count": 2000, "rank": 4},
            ],
        },
        {
            "category_id": "cat_10",
            "category_name": "产品管理",
            "aliases": ["产品经理"],
            "search_key": "产品经理",
            "source": "qcc_recruit",
            "cities": [
                {"city": "上海", "job_count": 9000, "rank": 1},
                {"city": "北京", "job_count": 8500, "rank": 2},
            ],
        },
    ]
    with p.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    supply_db.clear_cache()
    return p


def test_lookup_matches_direction(supply_fixture: Path):
    hit = supply_db.lookup_city_supply("数据分析", path=supply_fixture)
    assert hit["ok"] is True
    assert hit["category_name"] == "数据分析与大数据工程"
    assert hit["cities"][0]["city"] == "北京"
    assert hit["cities"][0]["job_count"] == 10000


def test_parse_city_rank_text():
    text = "北京 18620\n上海：1.2万\n广州 8,900\n深圳 12880"
    cities = supply_db.parse_city_rank_text(text)
    by_name = {c["city"]: c["job_count"] for c in cities}
    assert by_name["北京"] == 18620
    assert by_name["上海"] == 12000
    assert by_name["广州"] == 8900
    assert cities[0]["city"] == "北京"


def test_compute_stars_from_supply_db(supply_fixture: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(metrics_real, "_CONFIG_DIR", ROOT / "config" / "wind_agent")
    result = metrics_real.compute_city_supply_stars(
        "数据分析",
        supply_path=supply_fixture,
        prefer_qcc=True,
    )
    assert result["show_block"] is True
    assert result["source"] == "企查查招聘地区排行"
    assert result["cities"][0]["city"] == "北京"
    assert result["cities"][0]["stars"] == 5
    assert result["cities"][0]["difficulty"] == "较低"
    # 成都供给较低 → 难度不应低于头部城市
    chengdu = next(c for c in result["cities"] if c["city"] == "成都")
    assert chengdu["stars"] < result["cities"][0]["stars"]
    assert chengdu["difficulty"] in ("中等", "偏高")
