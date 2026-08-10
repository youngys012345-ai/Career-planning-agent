"""S0 Mock 工具：不连真库/真采/百炼，用于编排与版式评测。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from wind_agent import llm
from wind_agent.pack import EvidencePack


def clarify_intent(user_text: str = "", direction: str = "", cities: list[str] | None = None) -> dict[str, Any]:
    """解析意愿；支持模糊归一（如 agent算法工程师 → 算法）。"""
    from wind_agent.adapters.direction_alias import resolve_direction

    raw = (direction or "").strip()
    chosen = resolve_direction(user_text=user_text or "", direction=raw)
    d = (chosen.canonical or "").strip()
    if not d:
        return {
            "need_clarify": True,
            "options": ["数据分析", "产品经理", "后端开发", "算法", "__open__"],
            "prompt": "请选择意愿方向（最后一项可开放补充）",
        }
    extras = chosen.as_extras()
    if raw and raw != d and chosen.rewritten:
        extras = {**extras, "direction_chip": raw, "direction_from_query": chosen.original != raw}
    return {
        "need_clarify": False,
        "query_plan": {
            "direction": d,
            "cities": cities or ["全国主要城"],
            "user_query": user_text or "",
            "extras": extras,
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
            {
                "name": "SQL / 取数",
                "tier": "硬性门槛",
                "tag_class": "t-hard",
                "req": "任职要求高频出现",
                "blurb": "取数与多表关联是日常分析的基本功；窗口函数与查询优化在面试手撕中常见。",
                "score": 0.94,
            },
            {
                "name": "业务指标 / 分析方法",
                "tier": "硬性门槛",
                "tag_class": "t-hard",
                "req": "任职要求高频出现",
                "blurb": "能拆解留存、转化、漏斗等指标，是「会取数」与「能分析」的分界。",
                "score": 0.82,
            },
            {
                "name": "BI / 可视化",
                "tier": "高频加分项",
                "tag_class": "t-plus",
                "req": "中大厂岗位更常要求",
                "blurb": "看板与报表是常见交付物；Tableau / 帆软 / Power BI 居其一即可。",
                "score": 0.76,
            },
            {
                "name": "Python",
                "tier": "基础必备",
                "tag_class": "t-base",
                "req": "默认要求，极少单列",
                "blurb": "常用于清洗、批量处理与简易可视化；与 SQL 搭配覆盖多数专题分析。",
                "score": 0.58,
            },
        ],
        "majors": [
            {"name": "统计学 / 应用数学", "tier": "热招", "score": 0.42, "bar_score": 1.0},
            {"name": "计算机 / 软件", "tier": "热招", "score": 0.38, "bar_score": 0.9},
            {"name": "经济 / 金融", "tier": "有招·次热", "score": 0.22, "bar_score": 0.52},
        ],
        "direction": direction,
    }


def compute_city_supply_stars(direction: str) -> dict[str, Any]:
    return {
        "direction": direction,
        "cities": [
            {"city": "上海", "stars": 5, "label": "样本内供给最高档", "difficulty": "较低", "difficulty_class": "b-easy"},
            {"city": "北京", "stars": 4, "label": "相对高", "difficulty": "较低", "difficulty_class": "b-easy"},
            {"city": "杭州", "stars": 3, "label": "中等偏上", "difficulty": "中等", "difficulty_class": "b-mid"},
            {"city": "成都", "stars": 2, "label": "中等", "difficulty": "偏高", "difficulty_class": "b-hard"},
            {"city": "武汉", "stars": 1, "label": "相对较低", "difficulty": "偏高", "difficulty_class": "b-hard"},
            {"city": "西安", "stars": 1, "label": "相对较低", "difficulty": "偏高", "difficulty_class": "b-hard"},
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
    # 按方向给不同准备叙事，避免算法/后端仍套用数据分析 BI 话术
    if d in {"算法", "人工智能"} or "算法" in d:
        mid_goal = "做出可展示的模型/算法专题作品，补齐工程化能力"
        actions = [
            [
                f"每周固定练习 {focus} 中的 1–2 项：完成可复现实验（数据→特征/表示→训练→评估指标）。",
                "用课程或公开数据集走通一条最小训练链路，写清任务定义、基线与误差分析。",
                "整理技能清单与缺口：对照市场高频技能标出已会 / 学习中 / 未开始。",
            ],
            [
                "独立完成 1–2 个算法专题（分类/检索/生成或 CV/NLP 之一），附实验记录与可复现代码。",
                "补齐 Python 工程与基础部署能力（环境、日志、简单服务化），避免只会 notebook。",
                "练习把实验结论讲给非算法同学：任务、方法取舍、指标含义与局限。",
            ],
            [
                "挑 1 个更难任务做对比实验（换模型/特征/损失函数），写清假设、限制与验证方式。",
                "作品集迭代：突出问题背景、方法选择理由与指标提升，而非只堆框架名。",
                "对照分城供给与薪资认知做城市与准备节奏规划，保持市场信号复盘习惯。",
            ],
        ]
    elif d in {"后端开发", "前端开发", "测试"} or any(x in d for x in ("后端", "前端", "测试")):
        mid_goal = "形成可演示的工程作品，补齐中频技能"
        actions = [
            [
                f"每周固定练习 {focus} 中的 1–2 项，完成可运行小项目（含接口/页面与基础测试）。",
                "用课程项目走通「需求 → 设计 → 实现 → 自测」闭环，写清模块边界。",
                "整理技能清单与缺口：对照市场高频技能标出已会 / 学习中 / 未开始。",
            ],
            [
                "独立完成 1–2 个可演示系统（CRUD 服务、小工具或自动化脚本），附 README 与运行说明。",
                "补齐数据库/并发/工程规范短板中与方向最相关的 1–2 项。",
                "模拟技术沟通：用一页纸说明架构取舍、风险与下一步。",
            ],
            [
                "挑 1 个性能或稳定性问题做排查与优化，写清假设、验证与结果。",
                "作品集迭代：突出问题背景、方案理由与可维护性，而非只堆技术名词。",
                "对照分城供给与薪资认知做城市与准备节奏规划，保持市场信号复盘习惯。",
            ],
        ]
    elif d == "产品经理" or "产品" in d:
        mid_goal = "形成可展示的产品分析/方案作品，补齐中频技能"
        actions = [
            [
                f"每周固定练习 {focus} 中的 1–2 项：输出问题定义、用户画像与需求清单。",
                "用课程或实习场景走通「发现 → 方案 → 评审材料」一遍，写清成功指标。",
                "整理技能清单与缺口：对照市场高频技能标出已会 / 学习中 / 未开始。",
            ],
            [
                "独立完成 1–2 个产品专题（竞品拆解、需求文档或原型），能讲清取舍。",
                "补齐数据意识与原型表达短板，保证方案能落到指标与路径。",
                "模拟跨角色沟通：把方案改写成研发/运营都能看懂的版本。",
            ],
            [
                "挑 1 个复杂权衡题（范围/优先级/风险），写清假设、限制与验证方式。",
                "作品集迭代：突出问题背景、决策理由与业务影响，而非只堆方法论名词。",
                "对照分城供给与薪资认知做城市与准备节奏规划，保持市场信号复盘习惯。",
            ],
        ]
    else:
        mid_goal = "形成可展示的专题分析作品，补齐中频技能"
        actions = [
            [
                f"每周固定练习 {focus} 中的 1–2 项，完成可复现的小作业（含 SQL/取数与简单可视化）。",
                "用课程项目把「问题定义 → 数据准备 → 分析 → 结论」走通一遍，写清指标口径。",
                "整理个人技能清单与缺口：对照市场高频技能标出已会 / 学习中 / 未开始。",
            ],
            [
                "独立完成 1–2 个业务向专题（如留存、转化、运营复盘），输出报告与可复现笔记本。",
                "补齐 BI/可视化与 Python 数据处理短板，保证图表能讲清故事。",
                "模拟业务沟通：把分析结论改写成「给非技术同学看的一页纸建议」。",
            ],
            [
                "挑 1 个复杂指标拆解题（多表关联、漏斗或归因），写清假设、限制与验证方式。",
                "作品集迭代：突出问题背景、方法选择理由、业务影响，而非只堆工具名。",
                "对照分城供给与薪资认知做城市与准备节奏规划，保持市场信号复盘习惯。",
            ],
        ]
    return {
        "stages": [
            {
                "level": "初级",
                "goal": f"为大二起的{d}路径打底：核心工具与基础能力{hint}",
                "action_items": actions[0],
            },
            {
                "level": "中级",
                "goal": mid_goal,
                "action_items": actions[1],
            },
            {
                "level": "高级",
                "goal": "对齐校招高频要求，准备作品集与口径表达",
                "action_items": actions[2],
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
            if isinstance(parsed, list):
                stages = parsed
            elif isinstance(parsed, dict):
                stages = parsed.get("stages")
            else:
                stages = None
            if stages and isinstance(stages, list):
                return {"stages": stages, "model": llm.get_model()}
        except Exception:
            pass
    return _stub_capability_plan(skills, user_text=user_text, direction=direction)


def _stub_core_conclusions(pack_summary: dict[str, Any] | None) -> dict[str, Any]:
    summary = pack_summary or {}
    direction = summary.get("direction") or "目标方向"
    skills = [s.get("name") for s in (summary.get("skills") or []) if s.get("name")]
    majors = [m.get("name") for m in (summary.get("majors") or []) if m.get("name")]
    cities = summary.get("city_supply_stars") or []
    skill_text = "、".join(skills[:4]) if skills else "该方向常见核心技能"
    major_text = "、".join(majors[:3]) if majors else "相关对口专业"
    if cities:
        top_city = cities[0]
        city_text = f"样本内分城供给呈相对梯度，{top_city.get('city') or '头部城市'}相对更集中。"
    else:
        city_text = "样本内分城供给呈相对梯度，宜用星级理解相对岗位量。"
    return {
        "conclusions": [
            {
                "text": f"{direction}方向下，市场高频能力更集中在 {skill_text}。",
                "evidence": "依据：第3部分 技能词频",
            },
            {
                "text": f"专业侧更常见 {major_text}；其余专业有招但相对次热。",
                "evidence": "依据：第3部分 专业词频",
            },
            {
                "text": city_text,
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
            if isinstance(parsed, list):
                conclusions = parsed
            elif isinstance(parsed, dict):
                conclusions = parsed.get("conclusions")
            else:
                conclusions = None
            if conclusions and isinstance(conclusions, list):
                return {"conclusions": conclusions[:3], "model": llm.get_model()}
        except Exception:
            pass
    return _stub_core_conclusions(pack_summary)


_SOURCE_LABEL = {"zhilian": "智联招聘", "liepin": "猎聘", "boss": "BOSS直聘"}


def _source_platform_text(online: dict[str, Any], items: list[dict[str, Any]]) -> str:
    sources = online.get("sources") or sorted(
        {(x.get("source") or "").strip() for x in items if (x.get("source") or "").strip()}
    )
    return "、".join(_SOURCE_LABEL.get(s, s) for s in sources if s) or "在线招聘平台"


def _stub_wind_analysis(
    direction: str,
    items: list[dict[str, Any]],
    source_platform: str,
) -> str:
    n = len(items)
    titles = [x.get("job_title") or "" for x in items[:5] if x.get("job_title")]
    cities = sorted({(x.get("city") or "").strip() for x in items if (x.get("city") or "").strip()})
    title_hint = "、".join(titles[:3]) if titles else direction
    city_hint = "、".join(cities[:5]) if cities else "多城"
    return (
        f"基于本次在线浅采的 {n} 条「{direction}」相关岗位（数据来源：{source_platform}），"
        f"当前截面标题多集中在「{title_hint}」一类，地域覆盖包括 {city_hint}。"
        f"综合 JD 描述可见：业务取数、指标监控与报表/专题分析仍是主流交付；"
        f"部分岗位同时提到 Python/SQL 或可视化工具，呈现「分析+工具」双轨要求。"
        f"相较仅看离线历史库，在线截面更能反映近端标题用词与城市分布的即时构成，"
        f"建议把在线能力关键词与离线词频对照，优先补齐两边同时高频的技能。"
        f"（本段为 stub 降级文案，未调用模型。）"
    )


def build_latest_progress(
    online: dict[str, Any] | None = None,
    direction: str = "",
    user_query: str = "",
) -> dict[str, Any]:
    """求职风向：基于在线 JD 做综合风向分析（不展示公司/标题/城市卡片列表）。"""
    online = online or {}
    if not online.get("show_m9"):
        return {"show_m9": False, "title": "求职风向", "analysis": "", "source_platform": ""}

    items = online.get("items") or []
    source_platform = _source_platform_text(online, items)
    direction = direction or "目标方向"

    jd_blocks: list[str] = []
    for i, x in enumerate(items[:12], 1):
        desc = (x.get("description") or "").strip()
        jd_blocks.append(
            f"[{i}] 标题：{x.get('job_title') or '—'} | 城市：{x.get('city') or '—'} | "
            f"公司：{x.get('company') or '—'} | 来源：{_SOURCE_LABEL.get(x.get('source') or '', x.get('source') or '—')}\n"
            f"JD：{desc[:500] if desc else '（无详情摘要）'}"
        )
    jd_text = "\n\n".join(jd_blocks)

    system_prompt = (
        "你是「求职风向」分析模块，面向校招前期学生。"
        "任务：仅依据给定的在线浅采岗位样本（标题/城市/公司/JD 片段），写一份简短的风向变化与截面综合分析。"
        "要求：\n"
        "1) 输出 JSON：{\"analysis\":\"...\",\"highlights\":[\"要点1\",\"要点2\",\"要点3\"]}；"
        "analysis 为 180～320 字连贯段落，highlights 3 条短句。\n"
        "2) 综合讨论：岗位形态与标题用词、能力要求共性、地域/行业侧写（若样本有）、"
        "与「传统离线历史库印象」相比，本次在线截面可能意味着什么（机会新旧、能力侧重点）。\n"
        "3) 禁止编造样本中未出现的公司名、薪资数字、录用难度或「好不好进」。\n"
        "4) 不要输出公司清单、标题列表或城市枚举式罗列；要写成分析叙述。\n"
        "5) 个人背景只可作准备语境，不作人岗匹配结论。"
    )
    user_prompt = (
        f"用户提问：{user_query or '（未提供）'}\n"
        f"意愿方向：{direction}\n"
        f"数据来源平台：{source_platform}\n"
        f"在线合格样本数：{len(items)}\n\n"
        f"在线岗位样本：\n{jd_text}"
    )

    content = llm.chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    analysis = ""
    highlights: list[str] = []
    model_tag = "stub"
    if content:
        try:
            import json as _json

            parsed = _json.loads(llm.extract_json_text(content))
            if isinstance(parsed, dict):
                analysis = (parsed.get("analysis") or "").strip()
                hl = parsed.get("highlights") or []
                if isinstance(hl, list):
                    highlights = [str(x).strip() for x in hl if str(x).strip()][:5]
                if analysis:
                    model_tag = llm.get_model()
        except Exception:
            # JSON 解析失败时，若模型仍返回了较长正文，直接用作分析
            text = content.strip()
            if len(text) >= 80 and "{" not in text[:20]:
                analysis = text[:800]
                model_tag = llm.get_model()

    if not analysis:
        analysis = _stub_wind_analysis(direction, items, source_platform)
        highlights = [
            "在线截面反映近端岗位标题与能力表述",
            "宜与离线词频对照，优先补齐双边高频技能",
            f"数据来源：{source_platform}",
        ]

    return {
        "show_m9": True,
        "title": "求职风向",
        "analysis": analysis,
        "highlights": highlights,
        "source_platform": source_platform,
        "online_count": len(items),
        "mode": online.get("mode") or "",
        "model": model_tag,
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
