#!/usr/bin/env python
"""启动求职风向 Agent Web Demo（uvicorn）。

环境：
  - 公网展示：WIND_AGENT_ENV=public（默认）→ 0.0.0.0:8765
  - 公网反代：WIND_HOST=127.0.0.1（或 sync 时 WIND_BEHIND_PROXY=1）→ 仅本机，由 Nginx HTTPS 对外
  - 本地开发：WIND_AGENT_ENV=dev → 127.0.0.1:8766（仅本机）

可用环境变量覆盖：WIND_HOST / WIND_PORT / WIND_RELOAD
域名与反代说明见：docs/guide/public-https-reverse-proxy.md
"""

from __future__ import annotations

import os
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
        if key and key not in os.environ:
            os.environ[key] = val


def _resolve_bind() -> tuple[str, str, int, bool]:
    """返回 (环境名, host, port, reload)。"""
    env_name = (os.getenv("WIND_AGENT_ENV") or "public").strip().lower()
    if env_name in {"dev", "development", "local"}:
        env_name = "dev"
        default_host, default_port = "127.0.0.1", 8766
    else:
        env_name = "public"
        default_host, default_port = "0.0.0.0", 8765

    host = (os.getenv("WIND_HOST") or default_host).strip()
    port = int(os.getenv("WIND_PORT") or default_port)
    reload = (os.getenv("WIND_RELOAD") or ("1" if env_name == "dev" else "0")).strip() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return env_name, host, port, reload


def main() -> int:
    import uvicorn

    env_name, host, port, reload = _resolve_bind()
    display_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host

    print("求职风向 Agent Web Demo")
    print(f"  环境：{env_name}")
    print(f"  地址：http://{display_host}:{port}/")
    print(f"  健康：http://{display_host}:{port}/health")
    if env_name == "dev":
        print("  说明：开发服务默认仅本机可访问；公网展示请用 /opt 环境 + sync_to_public.sh")
    else:
        print("  说明：公网展示环境；开发请在 /home/projects 用 serve_dev.py")
        if host == "127.0.0.1":
            print("  反代：已仅本机监听，请用 Nginx HTTPS 对外（见 docs/guide/public-https-reverse-proxy.md）")
    print("  提示：复制 .env.example → .env 后按需配置模型密钥")

    uvicorn.run(
        "wind_agent.webapp:app",
        host=host,
        port=port,
        reload=reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
