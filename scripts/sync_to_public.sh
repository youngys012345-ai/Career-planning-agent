#!/usr/bin/env bash
# 将开发目录代码同步到公网展示环境（/opt），并重启公网服务。
# 仅在开发完成、需要对外发布时手动执行；日常开发请勿自动跑此脚本。
#
# 用法：
#   bash scripts/sync_to_public.sh
#   DEV_ROOT=... PUBLIC_ROOT=... bash scripts/sync_to_public.sh
set -euo pipefail

DEV_ROOT="${DEV_ROOT:-/home/projects/Career-planning-agent}"
PUBLIC_ROOT="${PUBLIC_ROOT:-/opt/Career-planning-agent}"
PUBLIC_PYTHON="${PUBLIC_PYTHON:-$PUBLIC_ROOT/.venv/bin/python}"

if [[ ! -d "$DEV_ROOT/src/wind_agent" ]]; then
  echo "错误：开发目录无效：$DEV_ROOT" >&2
  exit 1
fi
if [[ ! -d "$PUBLIC_ROOT" ]]; then
  echo "错误：公网目录不存在：$PUBLIC_ROOT" >&2
  exit 1
fi
if [[ ! -x "$PUBLIC_PYTHON" ]]; then
  echo "错误：找不到公网 Python：$PUBLIC_PYTHON" >&2
  exit 1
fi

echo "==> 同步开发 → 公网"
echo "    DEV:    $DEV_ROOT"
echo "    PUBLIC: $PUBLIC_ROOT"

# 不同步：.env、虚拟环境、运行时报告、缓存
rsync -a --delete \
  --exclude '__pycache__/' \
  --exclude '*.py[cod]' \
  --exclude '.pytest_cache/' \
  "$DEV_ROOT/src/" "$PUBLIC_ROOT/src/"

rsync -a \
  --exclude '__pycache__/' \
  "$DEV_ROOT/scripts/" "$PUBLIC_ROOT/scripts/"

if [[ -d "$DEV_ROOT/tests" ]]; then
  mkdir -p "$PUBLIC_ROOT/tests"
  rsync -a --delete \
    --exclude '__pycache__/' \
    --exclude '*.py[cod]' \
    --exclude '.pytest_cache/' \
    "$DEV_ROOT/tests/" "$PUBLIC_ROOT/tests/"
fi

if [[ -d "$DEV_ROOT/config" ]]; then
  rsync -a "$DEV_ROOT/config/" "$PUBLIC_ROOT/config/"
fi

if [[ -f "$DEV_ROOT/requirements.txt" ]]; then
  rsync -a "$DEV_ROOT/requirements.txt" "$PUBLIC_ROOT/requirements.txt"
fi

# 部署模板（Nginx 等），供备案后启用 HTTPS 反代
if [[ -d "$DEV_ROOT/deploy" ]]; then
  mkdir -p "$PUBLIC_ROOT/deploy"
  rsync -a --delete \
    --exclude '__pycache__/' \
    "$DEV_ROOT/deploy/" "$PUBLIC_ROOT/deploy/"
fi

# 同步离线快照库（企查查供给 / 薪资 / 校园详情），不含运行时报告
if [[ -d "$DEV_ROOT/data/snapshot" ]]; then
  mkdir -p "$PUBLIC_ROOT/data/snapshot"
  rsync -a --delete \
    --exclude '__pycache__/' \
    "$DEV_ROOT/data/snapshot/" "$PUBLIC_ROOT/data/snapshot/"
fi

# 记录最近一次发布时间（不含密钥）
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$PUBLIC_ROOT/.public_synced_at"
echo "$DEV_ROOT" > "$PUBLIC_ROOT/.public_synced_from"

echo "==> 重启公网服务 (WIND_AGENT_ENV=public)"
# 反代模式：仅本机监听，由 Nginx 对外提供 HTTPS
#   WIND_BEHIND_PROXY=1 bash scripts/sync_to_public.sh
BEHIND_PROXY="${WIND_BEHIND_PROXY:-0}"
if [[ "$BEHIND_PROXY" == "1" || "$BEHIND_PROXY" == "true" || "$BEHIND_PROXY" == "yes" ]]; then
  PUBLIC_HOST="127.0.0.1"
  echo "    模式：behind-proxy → 绑定 127.0.0.1:8765"
else
  PUBLIC_HOST="0.0.0.0"
  echo "    模式：直连 → 绑定 0.0.0.0:8765（建议备案后改为反代）"
fi

# 只结束公网目录下的 serve 进程，避免误杀开发服务
mapfile -t PIDS < <(pgrep -f "$PUBLIC_ROOT/.venv/bin/python $PUBLIC_ROOT/scripts/serve_wind_agent.py" || true)
if ((${#PIDS[@]})); then
  kill "${PIDS[@]}" 2>/dev/null || true
  sleep 1
fi

cd "$PUBLIC_ROOT"
export WIND_AGENT_ENV=public
export WIND_HOST="$PUBLIC_HOST"
export WIND_PORT=8765
export WIND_RELOAD=0
nohup "$PUBLIC_PYTHON" "$PUBLIC_ROOT/scripts/serve_wind_agent.py" \
  >"$PUBLIC_ROOT/data/reports/web/serve_public.log" 2>&1 &
echo $! >"$PUBLIC_ROOT/data/reports/web/serve_public.pid"
sleep 1

if curl -fsS "http://127.0.0.1:8765/health" >/dev/null; then
  echo "==> 公网健康检查通过：http://127.0.0.1:8765/health"
  if [[ "$PUBLIC_HOST" == "127.0.0.1" ]]; then
    echo "    外网请走 Nginx HTTPS（https://www.jobwindmark.bond）；勿再对公网开放 8765"
  else
    echo "    外网请用本机公网 IP:8765（安全组需放行）；上线域名后建议 WIND_BEHIND_PROXY=1"
  fi
else
  echo "警告：健康检查未通过，请查看 $PUBLIC_ROOT/data/reports/web/serve_public.log" >&2
  exit 1
fi
