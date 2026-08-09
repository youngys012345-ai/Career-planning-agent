"""S0 Mock 工具：不连真库/真采/百炼，用于编排与版式评测。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from wind_agent import llm
from wind_agent.pack import EvidencePack


def clarify_intent(user_text: str = "", direction: str = "", cities: list[str] | None = None) -> dict[str, Any]:
    """解析意愿；缺方向时返回 3+1 选项。"""
    d = (direction or "").strip()
    if not d:
        # 极简启发式：从文本抽关键词
        for cand in ("数据分析", "产品经理", "后端开发", "算法"):
            if cand in (user_text or ""):
                d = cand
                break
    if not d:
        return {
            "need_clarify": True,
            "options": ["数据分析", "产品经理", "后端开发", "__open__"],
            "prompt": "请选择意愿方向（第 4 项可开放补充）",
        }
    return {
        "need_clarify": False,
        "query_plan": {
            "direction": d,
            "cities": cities or ["全国主要城"],
            "user_query": user_text or "",
            "extras": {},
        },
    }


def online_job_search(direction: str, cities: list[str] | None = None, force_empty: bool = False) -> dict[str, Any]:
    """多站浅采 mock。"""
    if force_empty:
        return {"items": [], "sources": []}
    items = [
        {
            "source": "liepin",
            "company": "示例科技",
            "job_title": f"{direction}专员",
            "city": "上海",
            "description": "负责业务取数与报表",
        },
        {
            "source": "zhilian",
            "company": "示例零售",
            "job_title": f"{direction}助理",
            "city": "杭州",
            "description": "",
        },
        {
            "source": "boss",
            "company": "示例金融",
            "job_title": direction,
            "city": "北京",
            "description": "指标监控与专题分析",
        },
    ]
    return {"items": items, "sources": ["boss", "liepin", "zhilian"]}


def validate_online_jobs(items: list[dict[str, Any]] | None = None, min_qualified: int = 3) -> dict[str, Any]:
    """合格校验：至少需 company + job_title。"""
    items = items or []
    qualified = [
        x
        for x in items
        if (x.get("company") or "").strip() and (x.get("job_title") or "").strip()
    ]
    fields_available: list[str] = []
    for key in ("company", "job_title", "city", "description"):
        if any((q.get(key) or "").strip() for q in qualified):
            fields_available.append(key)
    show = len(qualified) >= min_qualified
    return {
        "qualified_count": len(qualified),
        "show_m9": show,
        "fields_available": fields_available,
        "items": qualified if show else [],
    }


def lookup_role_dictionary(direction: str) -> dict[str, Any]:
    catalog = {
        "数据分析": [
            {"name": "数据分析师", "tag": "业务分析"},
            {"name": "商业分析（BI）", "tag": "报表体系"},
            {"name": "数据开发工程师", "tag": "数仓/ETL"},
        ],
        "产品经理": [
            {"name": "C 端产品经理", "tag": "用户增长"},
            {"name": "B 端产品经理", "tag": "效率工具"},
            {"name": "数据产品经理", "tag": "数据资产"},
        ],
    }
    subroles = catalog.get(direction) or [
        {"name": f"{direction}相关岗位", "tag": "通用"},
    ]
    return {"direction": direction, "subroles": subroles}


def compute_skill_major_freq(direction: str) -> dict[str, Any]:
    return {
        "skills": [
            {"name": "SQL / 取数", "tier": "高频", "score": 0.94},
            {"name": "业务指标 / 分析方法", "tier": "高频", "score": 0.82},
            {"name": "BI / 可视化", "tier": "高频", "score": 0.76},
            {"name": "Python", "tier": "中频", "score": 0.58},
        ],
        "majors": [
            {"name": "统计学 / 应用数学", "tier": "热招", "score": 0.92},
            {"name": "计算机 / 软件", "tier": "热招", "score": 0.86},
            {"name": "经济 / 金融", "tier": "有招·次热", "score": 0.52},
        ],
        "direction": direction,
    }


def compute_city_supply_stars(direction: str) -> dict[str, Any]:
    return {
        "direction": direction,
        "cities": [
            {"city": "上海", "stars": 5, "label": "样本内供给最高档"},
            {"city": "北京", "stars": 4, "label": "相对高"},
            {"city": "杭州", "stars": 3, "label": "中等偏上"},
            {"city": "成都", "stars": 2, "label": "中等"},
            {"city": "武汉", "stars": 1, "label": "相对较低"},
            {"city": "西安", "stars": 1, "label": "相对较低"},
        ],
    }


def lookup_salary_freshgrad(
    direction: str,
    enable: bool = True,
) -> dict[str, Any]:
    """仅应届/1年以下；enable=False 模拟无数据。"""
    if not enable:
        return {"show_m6": False, "salary_by_city": None}
    return {
        "show_m6": True,
        "work_year": "lt_1y",
        "salary_by_city": [
            {
                "city": "上海",
                "mean_k": 16.0,
                "p25": 12.0,
                "p50": 15.0,
                "p75": 20.0,
                "distribution": [
                    {"bucket": "8-12k", "pct": 0.22},
                    {"bucket": "12-18k", "pct": 0.48},
                    {"bucket": "18k+", "pct": 0.30},
                ],
            },
            {
                "city": "杭州",
                "mean_k": 14.0,
                "p25": 10.0,
                "p50": 13.0,
                "p75": 17.0,
                "distribution": [
                    {"bucket": "8-12k", "pct": 0.30},
                    {"bucket": "12-18k", "pct": 0.50},
                    {"bucket": "18k+", "pct": 0.20},
                ],
            },
        ],
    }


def _stub_summarize_role_duties(
    subroles: list[dict[str, Any]],
    online_items: list[dict[str, Any]],
) -> dict[str, Any]:
    has_jd = any((x.get("description") or "").strip() for x in online_items)
    summaries = []
    for i, r in enumerate(subroles):
        source = "jd_context" if has_jd and i < 2 else "generated"
        name = r.get("name") or "岗位"
        summaries.append(
            {
                "name": name,
                "tag": r.get("tag"),
                "summary": (
                    f"{name}通常承接业务侧的数据问题：从需求澄清、取数口径确认，到指标监控与专题分析，"
                    f"再把结论沉淀成报表或汇报材料。日常会与产品、运营或数仓协作，强调可复现的分析过程与结果导向。"
                    f"校招前期可先对齐「能独立完成一次完整分析闭环」这一能力画像。"
                ),
                "source": source,
            }
        )
    return {"duty_summaries": summaries, "model": "stub"}


def summarize_role_duties(
    subroles: list[dict[str, Any]],
    online_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    online_items = online_items or []
    if not subroles:
        return {"duty_summaries": [], "model": "stub"}

    jd_snippets = [
        (x.get("description") or "").strip()[:700]
        for x in online_items
        if (x.get("description") or "").strip()
    ][:5]
    role_lines = "\n".join(
        f"- {r.get('name')}（{r.get('tag') or '通用'}）" for r in subroles
    )
    user_prompt = (
        "请为下列细分岗位各写 120–220 字的职责概括（约 3–5 句），面向校招前期准备："
        "写清日常工作内容、协作对象、交付物，不要编造薪资、录用难度或具体公司承诺。\n"
        f"子岗列表：\n{role_lines}\n"
    )
    if jd_snippets:
        user_prompt += f"\n可参考 JD 片段（仅作上下文，勿逐字照抄）：\n" + "\n---\n".join(jd_snippets)

    content = llm.chat(
        [
            {
                "role": "system",
                "content": (
                    "你是求职风向 Agent 的职责概括模块。"
                    "只输出 JSON 数组，每项含 name、summary、source（jd_context 或 generated）。"
                    "summary 必须充实、可操作，避免空泛一句话。"
                ),
            },
            {"role": "user", "content": user_prompt},
        ]
    )
    if content:
        try:
            import json as _json

            parsed = _json.loads(llm.extract_json_text(content))
            if isinstance(parsed, list) and parsed:
                summaries = []
                for i, r in enumerate(subroles):
                    item = parsed[i] if i < len(parsed) else {}
                    name = r.get("name") or item.get("name") or "岗位"
                    summaries.append(
                        {
                            "name": name,
                            "tag": r.get("tag"),
                            "summary": item.get("summary") or f"{name}职责概括",
                            "source": item.get("source") or ("jd_context" if jd_snippets else "generated"),
                        }
                    )
                return {"duty_summaries": summaries, "model": llm.get_model()}
        except Exception:
            pass

    return _stub_summarize_role_duties(subroles, online_items)


def _stub_capability_plan(
    skills: list[dict[str, Any]] | None,
    *,
    user_text: str = "",
    direction: str = "",
) -> dict[str, Any]:
    top = [s.get("name") for s in (skills or [])[:4] if s.get("name")]
    focus = "、".join(top) if top else "核心岗位能力"
    hint = f"（结合提问：{user_text[:40]}…）" if len(user_text) > 40 else (f"（结合提问：{user_text}）" if user_text else "")
    d = direction or "目标方向"
    return {
        "stages": [
            {
                "level": "初级",
                "goal": f"为大二起的{d}路径打底：工具 + 统计思维{hint}",
                "action_items": [
                    f"每周固定练习 {focus} 中的 1–2 项，完成可复现的小作业（含 SQL/取数与简单可视化）。",
                    "用课程项目把「问题定义 → 数据准备 → 分析 → 结论」走通一遍，写清指标口径。",
                    "整理个人技能清单与缺口：对照市场高频技能标出已会 / 学习中 / 未开始。",
                ],
            },
            {
                "level": "中级",
                "goal": "形成可展示的专题分析作品，补齐中频技能",
                "action_items": [
                    "独立完成 1–2 个业务向专题（如留存、转化、运营复盘），输出报告与可复现笔记本。",
                    "补齐 BI/可视化与 Python 数据处理短板，保证图表能讲清故事。",
                    "模拟业务沟通：把分析结论改写成「给非技术同学看的一页纸建议」。",
                ],
            },
            {
                "level": "高级",
                "goal": "对齐校招高频要求，准备作品集与口径表达",
                "action_items": [
                    "挑 1 个复杂指标拆解题（多表关联、漏斗或归因），写清假设、限制与验证方式。",
                    "作品集迭代：突出问题背景、方法选择理由、业务影响，而非只堆工具名。",
                    "对照分城供给与薪资认知做城市与准备节奏规划，保持市场信号复盘习惯。",
                ],
            },
        ],
        "model": "stub",
    }


def build_capability_plan(
    skills: list[dict[str, Any]] | None = None,
    user_text: str = "",
    direction: str = "",
    majors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    skill_lines = "\n".join(
        f"- {s.get('name')}（{s.get('tier') or '—'}）" for s in (skills or [])[:8] if s.get("name")
    )
    major_lines = "\n".join(
        f"- {m.get('name')}（{m.get('tier') or '—'}）" for m in (majors or [])[:5] if m.get("name")
    )
    content = llm.chat(
        [
            {
                "role": "system",
                "content": (
                    "你是求职准备规划模块。输出 JSON："
                    '{"stages":[{"level":"初级|中级|高级","goal":"...","action_items":["...","...","..."]}]}。'
                    "共 3 阶段；每阶段 goal 1 句，action_items 至少 3–5 条，每条写具体可执行动作与产出物。"
                    "个人背景只作时间与基础约束（如大二、统计学），禁止写成「专业匹配/适合」结论。"
                    "不要修改技能分档数字；不要编造就业难度。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"用户提问：{user_text or '（未提供）'}\n"
                    f"意愿方向：{direction or '（未指定）'}\n"
                    f"市场技能词频：\n{skill_lines or '（暂无）'}\n"
                    f"市场专业词频：\n{major_lines or '（暂无）'}\n"
                    "请制定更详细的初/中/高能力准备计划。"
                ),
            },
        ]
    )
    if content:
        try:
            import json as _json

            parsed = _json.loads(llm.extract_json_text(content))
            stages = parsed.get("stages") if isinstance(parsed, dict) else None
            if stages and isinstance(stages, list):
                return {"stages": stages, "model": llm.get_model()}
        except Exception:
            pass
    return _stub_capability_plan(skills, user_text=user_text, direction=direction)


def _stub_core_conclusions(pack_summary: dict[str, Any] | None) -> dict[str, Any]:
    direction = (pack_summary or {}).get("direction") or "目标方向"
    return {
        "conclusions": [
            {
                "text": f"{direction}方向下，市场高频能力集中在 SQL、业务指标与可视化工具。",
                "evidence": "依据：第3部分 技能词频",
            },
            {
                "text": "专业侧统计/计科出现更勤，经管类有招但相对次热。",
                "evidence": "依据：第3部分 专业词频",
            },
            {
                "text": "样本内分城供给呈相对梯度，宜用星级理解相对岗位量。",
                "evidence": "依据：第4部分 分城岗位供给",
            },
        ],
        "model": "stub",
    }


def build_core_conclusions(pack_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    summary = pack_summary or {}
    direction = summary.get("direction") or "目标方向"
    skills = summary.get("skills") or []
    majors = summary.get("majors") or []
    cities = summary.get("city_supply_stars") or []
    job_count = summary.get("job_count")

    city_parts = [f"{c.get('city')}{c.get('stars')}星" for c in cities[:6]]
    context = (
        f"方向：{direction}\n"
        f"用户提问：{summary.get('user_query') or '—'}\n"
        f"样本数：{job_count if job_count is not None else '—'}\n"
        f"技能 Top：{', '.join(s.get('name', '') for s in skills[:4])}\n"
        f"专业 Top：{', '.join(m.get('name', '') for m in majors[:3])}\n"
        f"分城星级：{', '.join(city_parts)}\n"
        "报告部分编号：第1部分结论；第2部分细分岗位；第3部分技能与专业；第4部分分城供给；"
        "第5部分薪资；第6部分求职风向；第7部分准备计划。\n"
    )
    content = llm.chat(
        [
            {
                "role": "system",
                "content": (
                    "你是求职风向结论模块。基于给定 Pack 摘要写恰好 3 条结论，"
                    '输出 JSON：{"conclusions":[{"text":"...","evidence":"依据：第N部分 …"}]}。'
                    "evidence 必须写「第N部分」中文编号，禁止写 M1/M3 等代号。"
                    "禁止编造 Pack 中未出现的数字；不得出现就业难度/好不好进等表述。"
                ),
            },
            {"role": "user", "content": context},
        ]
    )
    if content:
        try:
            import json as _json

            parsed = _json.loads(llm.extract_json_text(content))
            conclusions = parsed.get("conclusions") if isinstance(parsed, dict) else None
            if conclusions and isinstance(conclusions, list):
                return {"conclusions": conclusions[:3], "model": llm.get_model()}
        except Exception:
            pass
    return _stub_core_conclusions(pack_summary)


def build_latest_progress(online: dict[str, Any] | None = None) -> dict[str, Any]:
    """求职风向：仅基于在线浅采合格样本，不混入离线详情库。"""
    online = online or {}
    if not online.get("show_m9"):
        return {"show_m9": False, "cards": [], "title": "求职风向"}
    items = online.get("items") or []
    companies: list[str] = []
    for x in items:
        c = (x.get("company") or "").strip()
        if c and c not in companies:
            companies.append(c)
        if len(companies) >= 6:
            break
    titles: list[str] = []
    for x in items:
        t = (x.get("job_title") or "").strip()
        if t and t not in titles:
            titles.append(t)
        if len(titles) >= 6:
            break
    cities = sorted({(x.get("city") or "").strip() for x in items if (x.get("city") or "").strip()})
    sources = online.get("sources") or sorted(
        {(x.get("source") or "").strip() for x in items if (x.get("source") or "").strip()}
    )
    source_label = {
        "zhilian": "智联",
        "liepin": "猎聘",
        "boss": "BOSS",
    }
    source_text = "、".join(source_label.get(s, s) for s in sources) or "在线"

    cards = [
        {"k": "在线可见公司", "v": "、".join(companies) or "—"},
        {"k": "岗位标题簇", "v": "、".join(titles) or "—"},
        {"k": "出现城市", "v": "、".join(cities) or "—"},
        {"k": "浅采来源", "v": source_text},
    ]
    return {
        "show_m9": True,
        "cards": cards,
        "title": "求职风向",
        "mode": online.get("mode") or "",
        "note": online.get("note") or "在线浅采",
    }


def _template_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "render" / "templates"


def render_html_report(
    pack: EvidencePack | dict[str, Any],
    report_id: str = "",
) -> str:
    if isinstance(pack, dict):
        pack = EvidencePack.from_dict(pack)
    env = Environment(
        loader=FileSystemLoader(str(_template_dir())),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tpl = env.get_template("report.html")
    return tpl.render(pack=pack.to_dict(), report_id=report_id or "")
