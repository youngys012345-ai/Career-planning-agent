#!/usr/bin/env python
"""S1+S2 Demo：真指标 + 可选百炼生成 → HTML。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wind_agent.orchestrator import run_pipeline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="求职风向 Agent Demo（S1+S2）")
    parser.add_argument("--query", default="想往数据分析走，该补什么？")
    parser.add_argument("--direction", default="数据分析")
    parser.add_argument("--no-salary", action="store_true", help="模拟薪资库无数据")
    parser.add_argument("--no-online", action="store_true", help="模拟在线合格不足")
    parser.add_argument(
        "--show-hitl",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="报告中展示人在回路模块（默认开启）",
    )
    parser.add_argument(
        "--real-metrics",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="使用详情库真指标（默认开启）",
    )
    parser.add_argument(
        "--mock-all",
        action="store_true",
        help="强制全部 mock（含 M3/M4/词典）",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "data" / "reports" / "demo_mock.html"),
    )
    args = parser.parse_args()

    use_real = args.real_metrics and not args.mock_all

    pack, html = run_pipeline(
        user_text=args.query,
        direction=args.direction,
        use_real_metrics=use_real,
        salary_enable=not args.no_salary,
        online_force_empty=args.no_online,
        show_m11=args.show_hitl,
        report_id="localdemo01",
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    meta = out.with_suffix(".pack.json")
    meta.write_text(json.dumps(pack.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"HTML -> {out}")
    print(f"Pack -> {meta}")
    print(
        "flags:",
        {
            "is_mock": pack.flags.get("is_mock"),
            "show_m6": pack.flags.get("show_m6"),
            "show_m9": pack.flags.get("show_m9"),
            "qualified_count": pack.online.get("qualified_count"),
            "job_count": (pack.metrics.get("metrics_meta") or {}).get("job_count"),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
