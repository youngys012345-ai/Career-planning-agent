"""求职风向 Agent · FastAPI Web Demo（对接 orchestrator.run_pipeline）。"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from wind_agent.orchestrator import hitl_update_constraints, run_pipeline
from wind_agent.pack import EvidencePack
from wind_agent.tools.mock_tools import render_html_report

# 报告持久化目录
REPORTS_DIR = Path(__file__).resolve().parents[2] / "data" / "reports" / "web"


class ReportRequest(BaseModel):
    """生成风向报告请求体。"""

    query: str = Field(default="想往数据分析走", description="用户自然语言意愿")
    direction: str | None = Field(default=None, description="可选：已确定的方向")
    cities: list[str] | None = Field(default=None, description="可选：关注城市列表")
    use_real_metrics: bool = Field(
        default=True,
        description="是否使用详情库真指标（技能/专业/供给）",
    )


class HitlRequest(BaseModel):
    """人在回路：仅改方向/城市后重算。"""

    report_id: str
    direction: str | None = None
    cities: list[str] | None = None


def _dashscope_configured() -> bool:
    key = (os.getenv("DASHSCOPE_API_KEY") or "").strip()
    return bool(key and key != "sk-xxxxxxxx")


def _model_mode() -> str:
    return "dashscope" if _dashscope_configured() else "stub"


def _pack_path(report_id: str) -> Path:
    return REPORTS_DIR / f"{report_id}.pack.json"


def _html_path(report_id: str) -> Path:
    return REPORTS_DIR / f"{report_id}.html"


def _save_report(report_id: str, pack: EvidencePack, html: str) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    _html_path(report_id).write_text(html, encoding="utf-8")
    _pack_path(report_id).write_text(
        json.dumps(pack.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_pack(report_id: str) -> EvidencePack:
    path = _pack_path(report_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="报告上下文不存在或已过期")
    return EvidencePack.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _pack_summary(pack: EvidencePack) -> dict[str, Any]:
    return {
        "direction": pack.query_plan.direction,
        "cities": pack.query_plan.cities,
        "qualified_count": pack.online.get("qualified_count", 0),
        "online_mode": pack.online.get("mode"),
        "conclusions_count": len(pack.generated.get("conclusions") or []),
        "is_mock": bool(pack.flags.get("is_mock")),
        "dashscope_configured": _dashscope_configured(),
        "model_mode": _model_mode(),
    }


def _run_and_save(
    *,
    query: str,
    direction: str | None,
    cities: list[str] | None,
    use_real_metrics: bool,
) -> tuple[str, EvidencePack, str]:
    """调用编排并写入 HTML / Pack，返回 (report_id, pack, html)。"""
    report_id = uuid.uuid4().hex[:12]
    pack, html = run_pipeline(
        user_text=query,
        direction=direction or "",
        cities=cities,
        use_real_metrics=use_real_metrics,
        salary_enable=True,
        online_force_empty=False,
        show_m11=True,
        report_id=report_id,
    )
    # 再渲染一次，确保 report_id / HITL 脚本写入
    html = render_html_report(pack, report_id=report_id)
    _save_report(report_id, pack, html)
    return report_id, pack, html


def _landing_page_html() -> str:
    dashscope_ok = _dashscope_configured()
    model_hint = (
        "已检测到 DASHSCOPE_API_KEY，生成链路可走 DashScope（qwen-plus 等）。"
        if dashscope_ok
        else "当前未配置 DASHSCOPE_API_KEY，结论/职责/准备计划使用本地 stub。"
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>求职风向 Agent</title>
<style>
  @import url("https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;700&family=Noto+Sans+SC:wght@400;500;600;700&display=swap");
  :root {{
    --sea: #0d6e6e; --sea-deep: #084848; --sand: #c4a35a;
    --bg: #eef3f1; --ink: #0f1c1a; --ink2: #3d4f4b; --ink3: #7a8c87; --line: #d5e0dc;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
    background:
      radial-gradient(ellipse 80% 50% at 10% -10%, #d4ebe6 0%, transparent 55%),
      radial-gradient(ellipse 60% 40% at 100% 0%, #f0e6c8 0%, transparent 45%),
      var(--bg);
    color: var(--ink); line-height: 1.65; padding: 24px 16px 48px;
  }}
  .wrap {{ max-width: 640px; margin: 0 auto; }}
  .gate {{
    background: #fff; border: 1px solid var(--line); border-radius: 12px; padding: 22px 24px;
  }}
  .brand {{
    font-family: "Noto Serif SC", serif; font-size: 28px; font-weight: 700;
    color: var(--sea-deep); letter-spacing: .04em;
  }}
  .tagline {{ font-size: 13px; color: var(--ink2); margin-top: 6px; max-width: 36em; }}
  .chip {{
    display: inline-block; font-size: 11px; font-weight: 600; background: var(--sand);
    color: #1a1508; border-radius: 999px; padding: 3px 10px; margin-bottom: 10px;
  }}
  label {{ display: block; font-size: 13px; font-weight: 600; margin-top: 14px; }}
  input, textarea {{
    width: 100%; margin-top: 6px; padding: 10px 12px; border: 1px solid var(--line);
    border-radius: 8px; font-size: 14px; font-family: inherit; background: #f4faf8;
  }}
  textarea {{ min-height: 72px; resize: vertical; }}
  .opts {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }}
  .opt {{
    border: 1px solid var(--sea); background: #fff; color: var(--sea-deep);
    border-radius: 8px; padding: 8px 14px; font-size: 13px; cursor: pointer;
  }}
  .opt.on {{ background: var(--sea); color: #fff; }}
  button {{
    margin-top: 18px; width: 100%; padding: 12px; border: none; border-radius: 8px;
    background: linear-gradient(145deg, #084848, #0d6e6e); color: #fff; font-size: 15px;
    font-weight: 600; cursor: pointer;
  }}
  button:disabled {{ opacity: 0.6; cursor: wait; }}
  .hint {{ margin-top: 10px; font-size: 11px; color: var(--ink3); }}
  .foot {{ font-size: 11px; color: var(--ink3); margin-top: 18px; }}
  #status {{ margin-top: 12px; font-size: 13px; min-height: 1.2em; }}
  .err {{ color: #b33; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="gate">
    <span class="chip">Market-first · 意愿驱动</span>
    <div class="brand">求职风向</div>
    <p class="tagline">按你的<strong>意愿方向</strong>读市场要什么能力与如何准备——不是用已有条件做岗位匹配。</p>
    <form id="f">
      <label for="query">你的意愿 / 问题</label>
      <textarea id="query" name="query" placeholder="例：想往数据分析走，该补什么？">我现在是大二统计专业学生，以后想找数据分析岗位工作，我应该如何准备。</textarea>

      <label for="direction">方向（可点选或手填）</label>
      <div class="opts" id="dirOpts">
        <span class="opt on" data-v="数据分析">数据分析</span>
        <span class="opt" data-v="产品经理">产品经理</span>
        <span class="opt" data-v="后端开发">后端开发</span>
        <span class="opt" data-v="__open__">其他（手填）</span>
      </div>
      <input id="direction" name="direction" type="text" value="数据分析" placeholder="开放方向时在此填写">

      <button type="submit" id="btn">生成风向报告</button>
      <div id="status"></div>
      <p class="hint">报告底部支持人在回路：可改方向/城市后局部重算。</p>
    </form>
  </div>
  <div class="foot">
    <p><strong>数据：</strong>技能/专业/供给读往届招聘详情库；预期薪资读猎聘薪资库；求职风向为在线浅采（智联等）。</p>
    <p><strong>模型：</strong>{model_hint}</p>
    <p>启动：<code>python scripts/serve_wind_agent.py</code> · 配置 <code>.env</code> 中 <code>DASHSCOPE_API_KEY</code>。</p>
  </div>
</div>
<script>
const dirInput = document.getElementById("direction");
document.querySelectorAll("#dirOpts .opt").forEach((el) => {{
  el.addEventListener("click", () => {{
    document.querySelectorAll("#dirOpts .opt").forEach((x) => x.classList.remove("on"));
    el.classList.add("on");
    const v = el.getAttribute("data-v");
    if (v === "__open__") {{ dirInput.value = ""; dirInput.focus(); }}
    else dirInput.value = v;
  }});
}});
document.getElementById("f").addEventListener("submit", async (e) => {{
  e.preventDefault();
  const btn = document.getElementById("btn");
  const status = document.getElementById("status");
  btn.disabled = true;
  status.textContent = "正在取数 / 计算 / 调用百炼生成…";
  status.className = "";
  try {{
    const body = {{
      query: document.getElementById("query").value.trim(),
      direction: document.getElementById("direction").value.trim() || null,
      use_real_metrics: true
    }};
    const res = await fetch("/api/report", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify(body)
    }});
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "生成失败");
    window.location.href = data.html_url;
  }} catch (err) {{
    status.textContent = err.message || "请求失败";
    status.className = "err";
    btn.disabled = false;
  }}
}});
</script>
</body>
</html>"""


def create_app() -> FastAPI:
    """构建 FastAPI 应用实例。"""
    app = FastAPI(
        title="求职风向 Agent",
        description="校招 Market-first 风向简报 Web Demo",
        version="0.1.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _landing_page_html()

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "wind_agent",
            "dashscope_configured": _dashscope_configured(),
            "model_mode": _model_mode(),
            "reports_dir": str(REPORTS_DIR),
        }

    @app.post("/api/report")
    def api_report(req: ReportRequest) -> JSONResponse:
        try:
            report_id, pack, html = _run_and_save(
                query=req.query,
                direction=req.direction,
                cities=req.cities,
                use_real_metrics=req.use_real_metrics,
            )
        except Exception as exc:  # noqa: BLE001 — Demo 需返回可读错误
            raise HTTPException(status_code=500, detail=f"报告生成失败：{exc}") from exc

        payload = {
            "id": report_id,
            "html_url": f"/report/{report_id}",
            "flags": dict(pack.flags),
            "pack_summary": _pack_summary(pack),
            "html_length": len(html),
        }
        return JSONResponse(content=payload)

    @app.post("/api/hitl")
    def api_hitl(req: HitlRequest) -> JSONResponse:
        if not req.report_id.isalnum() or len(req.report_id) > 32:
            raise HTTPException(status_code=400, detail="无效报告 ID")
        old = _load_pack(req.report_id)
        new_id = uuid.uuid4().hex[:12]
        try:
            pack, html = hitl_update_constraints(
                old,
                direction=req.direction,
                cities=req.cities,
                use_real_metrics=not bool(old.flags.get("is_mock")),
                show_m11=True,
                report_id=new_id,
            )
            html = render_html_report(pack, report_id=new_id)
            _save_report(new_id, pack, html)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"重算失败：{exc}") from exc
        return JSONResponse(
            content={
                "id": new_id,
                "html_url": f"/report/{new_id}",
                "pack_summary": _pack_summary(pack),
            }
        )

    @app.get("/report/{report_id}")
    def view_report(report_id: str) -> FileResponse:
        if not report_id.isalnum() or len(report_id) > 32:
            raise HTTPException(status_code=400, detail="无效报告 ID")
        path = _html_path(report_id)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="报告不存在或已过期")
        return FileResponse(path, media_type="text/html; charset=utf-8")

    return app


# uvicorn 默认入口：wind_agent.webapp:app
app = create_app()
