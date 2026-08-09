"""Supervisor 编排：G1∥G2 → G3 → G4 → render（S0 用确定性调度模拟多 Agent）。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from wind_agent.adapters import job_db
from wind_agent.pack import EvidencePack, QueryPlan
from wind_agent.registry import ToolRegistry
from wind_agent.tools import metrics_real, mock_tools, online_shallow, salary_db


def build_default_registry(*, use_real_metrics: bool = True) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register("clarify_intent", "意愿追问与方向解析", mock_tools.clarify_intent)
    if use_real_metrics:
        reg.register("online_job_search", "多站浅采（在线）", online_shallow.online_job_search, "G1")
        reg.register("lookup_role_dictionary", "细分岗位词典", metrics_real.lookup_role_dictionary, "G2")
        reg.register("compute_skill_major_freq", "技能与专业词频", metrics_real.compute_skill_major_freq, "G2")
        reg.register("compute_city_supply_stars", "分城供给星级", metrics_real.compute_city_supply_stars, "G2")
        reg.register("lookup_salary_freshgrad", "应届薪资库查询", salary_db.lookup_salary_freshgrad, "G2")
    else:
        reg.register("online_job_search", "多站浅采（mock）", mock_tools.online_job_search, "G1")
        reg.register("lookup_role_dictionary", "细分岗位词典", mock_tools.lookup_role_dictionary, "G2")
        reg.register("compute_skill_major_freq", "技能与专业词频", mock_tools.compute_skill_major_freq, "G2")
        reg.register("compute_city_supply_stars", "分城供给星级", mock_tools.compute_city_supply_stars, "G2")
        reg.register("lookup_salary_freshgrad", "应届薪资库查询", mock_tools.lookup_salary_freshgrad, "G2")

    reg.register("validate_online_jobs", "在线合格校验", mock_tools.validate_online_jobs, "G1")
    reg.register("summarize_role_duties", "职责 Agent 概括", mock_tools.summarize_role_duties, "G3")
    reg.register("build_capability_plan", "初中高能力准备计划", mock_tools.build_capability_plan, "G3")
    reg.register("build_core_conclusions", "核心结论×3", mock_tools.build_core_conclusions, "G4")
    reg.register("build_latest_progress", "求职风向（在线）", mock_tools.build_latest_progress)
    reg.register("render_html_report", "渲染 HTML 报告", mock_tools.render_html_report)
    return reg


def _jd_context_items(direction: str, *, use_real: bool, online_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """职责概括用的 JD 上下文：优先在线片段，不足时补详情库。"""
    items = [x for x in online_items if (x.get("description") or "").strip()]
    if len(items) >= 2:
        return items[:8]
    if use_real:
        jobs = job_db.filter_jobs(direction)[:8]
        for j in jobs:
            desc = (j.get("description") or "").strip()
            if not desc:
                continue
            items.append(
                {
                    "company": j.get("company_name") or j.get("company_name_raw") or "",
                    "job_title": j.get("job_title") or "",
                    "city": j.get("city") or "",
                    "description": desc[:800],
                }
            )
    return items[:8]


def _annotate_salary_bars(salary_by_city: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """为均数条形图计算相对宽度（左对齐，按均数比例延伸）。"""
    rows = list(salary_by_city or [])
    if not rows:
        return []
    mx = max(float(r.get("mean_k") or 0) for r in rows) or 1.0
    out: list[dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        mean = float(r.get("mean_k") or 0)
        item["bar_pct"] = round(100.0 * mean / mx, 1)
        out.append(item)
    return out


def run_pipeline(
    user_text: str = "想往数据分析走",
    *,
    direction: str = "",
    cities: list[str] | None = None,
    registry: ToolRegistry | None = None,
    use_real_metrics: bool = True,
    salary_enable: bool = True,
    online_force_empty: bool = False,
    show_m11: bool = True,
    report_id: str = "",
) -> tuple[EvidencePack, str]:
    reg = registry or build_default_registry(use_real_metrics=use_real_metrics)

    intent = reg.call("clarify_intent", user_text=user_text, direction=direction, cities=cities)
    if intent.get("need_clarify"):
        # S0：自动选第一项以便评测；正式版应交前端
        direction = intent["options"][0]
        intent = reg.call("clarify_intent", user_text=user_text, direction=direction, cities=cities)

    qp = intent["query_plan"]
    pack = EvidencePack(
        query_plan=QueryPlan(
            direction=qp["direction"],
            cities=list(qp.get("cities") or ["全国主要城"]),
            user_query=user_text or qp.get("user_query") or "",
            extras=dict(qp.get("extras") or {}),
        ),
        flags={
            "show_m6": False,
            "show_m9": False,
            "show_m11": show_m11,
            "is_mock": not use_real_metrics,
        },
    )

    # G1 ∥ G2
    with ThreadPoolExecutor(max_workers=4) as ex:
        fut_online = ex.submit(
            reg.call,
            "online_job_search",
            direction=pack.query_plan.direction,
            cities=pack.query_plan.cities,
            force_empty=online_force_empty,
        )
        fut_roles = ex.submit(reg.call, "lookup_role_dictionary", direction=pack.query_plan.direction)
        fut_sm = ex.submit(reg.call, "compute_skill_major_freq", direction=pack.query_plan.direction)
        fut_city = ex.submit(reg.call, "compute_city_supply_stars", direction=pack.query_plan.direction)
        fut_sal = ex.submit(
            reg.call,
            "lookup_salary_freshgrad",
            direction=pack.query_plan.direction,
            enable=salary_enable,
        )
        online_raw = fut_online.result()
        roles = fut_roles.result()
        sm = fut_sm.result()
        city = fut_city.result()
        sal = fut_sal.result()

    validated = reg.call("validate_online_jobs", items=online_raw.get("items") or [])
    pack.online = {
        "qualified_count": validated["qualified_count"],
        "show_m9": validated["show_m9"],
        "fields_available": validated["fields_available"],
        "items": validated["items"],
        "sources": online_raw.get("sources") or [],
        "mode": online_raw.get("mode") or "",
        "note": online_raw.get("note") or "",
    }

    pack.roles = {"subroles": roles.get("subroles") or []}
    salary_source = sal.get("source") or ("liepin_salary_v0" if use_real_metrics else "salary_db_mock")
    pack.metrics = {
        "skills": sm.get("skills") or [],
        "majors": sm.get("majors") or [],
        "city_supply_stars": city.get("cities") or [],
        "salary_by_city": _annotate_salary_bars(sal.get("salary_by_city")),
        "salary_meta": {
            "work_year": sal.get("work_year") or "lt_1y",
            "source": salary_source,
            "category_name": sal.get("category_name"),
            "national_lt1y_k": sal.get("national_lt1y_k"),
            "sample_count": sal.get("sample_count"),
        },
        "metrics_meta": {
            "source": "往届公司招聘信息",
            "job_count": sm.get("job_count"),
        },
    }
    pack.flags["show_m6"] = bool(sal.get("show_m6"))

    jd_items = _jd_context_items(
        pack.query_plan.direction,
        use_real=use_real_metrics,
        online_items=pack.online.get("items") or [],
    )

    # G3 并行
    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_duty = ex.submit(
            reg.call,
            "summarize_role_duties",
            subroles=pack.roles["subroles"],
            online_items=jd_items,
        )
        fut_plan = ex.submit(
            reg.call,
            "build_capability_plan",
            skills=pack.metrics["skills"],
            user_text=pack.query_plan.user_query,
            direction=pack.query_plan.direction,
            majors=pack.metrics["majors"],
        )
        duties = fut_duty.result()
        plan = fut_plan.result()

    pack.roles["duty_summaries"] = duties.get("duty_summaries") or []
    pack.generated["prep_plan"] = plan.get("stages") or []

    latest = reg.call("build_latest_progress", online=pack.online)
    pack.generated["latest"] = latest
    pack.flags["show_m9"] = bool(latest.get("show_m9"))

    conclusions = reg.call(
        "build_core_conclusions",
        pack_summary={
            "direction": pack.query_plan.direction,
            "skills": pack.metrics.get("skills") or [],
            "majors": pack.metrics.get("majors") or [],
            "city_supply_stars": pack.metrics.get("city_supply_stars") or [],
            "job_count": (pack.metrics.get("metrics_meta") or {}).get("job_count"),
            "user_query": pack.query_plan.user_query,
        },
    )
    pack.generated["conclusions"] = conclusions.get("conclusions") or []
    models = {
        duties.get("model"),
        plan.get("model"),
        conclusions.get("model"),
    }
    real_models = {m for m in models if m and m != "stub"}
    pack.generated["model_tag"] = (
        f"百炼 {next(iter(real_models))}" if real_models else "生成 stub"
    )

    html = reg.call(
        "render_html_report",
        pack=pack,
        report_id=report_id,
    )
    return pack, html


def hitl_update_constraints(
    pack: EvidencePack,
    *,
    direction: str | None = None,
    cities: list[str] | None = None,
    registry: ToolRegistry | None = None,
    **pipeline_kwargs: Any,
) -> tuple[EvidencePack, str]:
    """M11：仅允许改方向/城市后局部重跑。"""
    new_direction = direction if direction is not None else pack.query_plan.direction
    new_cities = cities if cities is not None else pack.query_plan.cities
    return run_pipeline(
        user_text=pack.query_plan.user_query or "",
        direction=new_direction,
        cities=new_cities,
        registry=registry,
        **pipeline_kwargs,
    )
