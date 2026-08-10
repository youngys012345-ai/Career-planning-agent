#!/usr/bin/env python
"""启动本地开发 Web（仅本机 127.0.0.1:8766，默认热重载）。

用法（推荐用公网机上的 venv，避免重复装依赖）：
  /opt/Career-planning-agent/.venv/bin/python scripts/serve_dev.py

或在本仓库创建 .venv 后：
  .venv/bin/python scripts/serve_dev.py
"""

from __future__ import annotations

import os
import runpy
from pathlib import Path

# 强制开发绑定；可用 WIND_HOST / WIND_PORT 覆盖
os.environ.setdefault("WIND_AGENT_ENV", "dev")
os.environ.setdefault("WIND_HOST", "127.0.0.1")
os.environ.setdefault("WIND_PORT", "8766")
os.environ.setdefault("WIND_RELOAD", "1")

# 复用同目录下的 serve_wind_agent 入口
serve = Path(__file__).resolve().with_name("serve_wind_agent.py")
runpy.run_path(str(serve), run_name="__main__")
