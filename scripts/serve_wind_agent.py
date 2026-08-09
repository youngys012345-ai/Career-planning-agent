#!/usr/bin/env python
"""启动求职风向 Agent Web Demo（uvicorn）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# 尝试加载 .env（不存在时静默跳过）
_env = ROOT / ".env"
if _env.is_file():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key and key not in __import__("os").environ:
            __import__("os").environ[key] = val


def main() -> int:
    import uvicorn

    print("求职风向 Agent Web Demo")
    print("  地址：http://127.0.0.1:8765/")
    print("  健康：http://127.0.0.1:8765/health")
    print("  提示：复制 .env.example → .env 后按需配置模型密钥")
    uvicorn.run(
        "wind_agent.webapp:app",
        host="0.0.0.0",
        port=8765,
        reload=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
