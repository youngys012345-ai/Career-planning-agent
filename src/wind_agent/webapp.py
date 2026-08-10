"""求职风向 Agent · FastAPI Web Demo（对接 orchestrator.run_pipeline）。"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field

from wind_agent.orchestrator import hitl_update_constraints, run_pipeline
from wind_agent.pack import EvidencePack
from wind_agent.tools.mock_tools import render_html_report

# 报告持久化目录
REPORTS_DIR = Path(__file__).resolve().parents[2] / "data" / "reports" / "web"
# 静态资源与 Jinja 模板目录
STATIC_DIR = Path(__file__).resolve().parent / "static"
TEMPLATES_DIR = Path(__file__).resolve().parent / "render" / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


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
    """人在回路：追问 / 快捷动作 / 改方向城市后重算。"""

    report_id: str
    direction: str | None = None
    cities: list[str] | None = None
    followup: str | None = None
    action: str | None = Field(
        default=None,
        description="reject_conclusion | exclude_jobs | switch_direction | regenerate",
    )


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


def _static_asset_version() -> str:
    """用静态资源 mtime 做缓存破坏，避免公网浏览器继续用旧 JS。"""
    newest = 0
    for rel in ("js/landing.js", "js/motion.js", "css/landing.css", "css/motion.css"):
        path = STATIC_DIR / rel
        try:
            newest = max(newest, int(path.stat().st_mtime))
        except OSError:
            continue
    return str(newest or 1)


def _landing_page_html() -> str:
    """渲染首页 Jinja 模板。"""
    return _jinja_env.get_template("index.html").render(asset_v=_static_asset_version())


def create_app() -> FastAPI:
    """构建 FastAPI 应用实例。"""
    app = FastAPI(
        title="求职风向 Agent",
        description="校招 Market-first 风向简报 Web Demo",
        version="0.1.0",
    )

    # 静态资源需在具体路由之后挂载亦可；放在路由定义前挂载时注意与 / 不冲突
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
                followup=req.followup or "",
                action=req.action or "",
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

    # 挂载静态资源（放在 API 路由之后，避免遮蔽业务路径）
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app


# uvicorn 默认入口：wind_agent.webapp:app
app = create_app()
