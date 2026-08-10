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

# 记录最近一次发布时间（不含密钥）
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$PUBLIC_ROOT/.public_synced_at"
echo "$DEV_ROOT" > "$PUBLIC_ROOT/.public_synced_from"

echo "==> 重启公网服务 (WIND_AGENT_ENV=public, :8765)"
# 只结束公网目录下的 serve 进程，避免误杀开发服务
mapfile -t PIDS < <(pgrep -f "$PUBLIC_ROOT/.venv/bin/python $PUBLIC_ROOT/scripts/serve_wind_agent.py" || true)
if ((${#PIDS[@]})); then
  kill "${PIDS[@]}" 2>/dev/null || true
  sleep 1
fi

cd "$PUBLIC_ROOT"
export WIND_AGENT_ENV=public
export WIND_HOST=0.0.0.0
export WIND_PORT=8765
export WIND_RELOAD=0
nohup "$PUBLIC_PYTHON" "$PUBLIC_ROOT/scripts/serve_wind_agent.py" \
  >"$PUBLIC_ROOT/data/reports/web/serve_public.log" 2>&1 &
echo $! >"$PUBLIC_ROOT/data/reports/web/serve_public.pid"
sleep 1

if curl -fsS "http://127.0.0.1:8765/health" >/dev/null; then
  echo "==> 公网健康检查通过：http://127.0.0.1:8765/health"
  echo "    外网请用本机公网 IP:8765（安全组需放行）"
else
  echo "警告：健康检查未通过，请查看 $PUBLIC_ROOT/data/reports/web/serve_public.log" >&2
  exit 1
fi
