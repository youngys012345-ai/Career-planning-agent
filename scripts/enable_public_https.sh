#!/usr/bin/env bash
# 备案通过且 DNS 已指向本机后：启用 Nginx HTTPS 反代 + 应用仅本机监听
# 用法：
#   bash scripts/enable_public_https.sh
#   DOMAIN=www.jobwindmark.bond bash scripts/enable_public_https.sh
set -euo pipefail

DOMAIN="${DOMAIN:-www.jobwindmark.bond}"
APEX="${APEX:-jobwindmark.bond}"
DEV_ROOT="${DEV_ROOT:-/home/projects/Career-planning-agent}"
PUBLIC_ROOT="${PUBLIC_ROOT:-/opt/Career-planning-agent}"
CONF_SRC="$DEV_ROOT/deploy/nginx/jobwindmark.bond.conf"
LIMIT_SRC="$DEV_ROOT/deploy/nginx/wind_agent_limit_req.conf"

echo "==> 检查本机公网 IP"
MYIP="$(curl -4 -fsS --max-time 8 ifconfig.me || curl -4 -fsS --max-time 8 icanhazip.com || true)"
MYIP="$(echo "$MYIP" | tr -d '[:space:]')"
if [[ -z "$MYIP" ]]; then
  echo "错误：无法获取本机公网 IP" >&2
  exit 1
fi
echo "    本机公网 IP: $MYIP"

echo "==> 检查 DNS A 记录 → $DOMAIN"
RESOLVED="$(dig +short "$DOMAIN" A | grep -E '^[0-9.]+$' | head -1 || true)"
if [[ -z "$RESOLVED" ]]; then
  echo "错误：域名 $DOMAIN 尚无 A 记录。" >&2
  echo "请到万网/阿里云 DNS 添加：" >&2
  echo "  主机记录 www   类型 A   值 $MYIP" >&2
  echo "  主机记录 @     类型 A   值 $MYIP   （可选，用于裸域跳转）" >&2
  exit 1
fi
echo "    DNS 解析到: $RESOLVED"
if [[ "$RESOLVED" != "$MYIP" ]]; then
  echo "错误：DNS($RESOLVED) 与本机公网 IP($MYIP) 不一致，请先改解析。" >&2
  exit 1
fi

if [[ ! -f "$CONF_SRC" ]]; then
  echo "错误：缺少配置 $CONF_SRC" >&2
  exit 1
fi

echo "==> 确保 Nginx / Certbot 已安装"
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -qq nginx certbot python3-certbot-nginx >/dev/null
mkdir -p /var/www/certbot

# 先放一个仅 80 的引导站，方便 ACME；证书就绪后再换完整 HTTPS conf
BOOT="/etc/nginx/sites-available/jobwindmark.bond.bootstrap.conf"
cat >"$BOOT" <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name $DOMAIN $APEX;
    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
        default_type "text/plain";
    }
    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
ln -sfn "$BOOT" /etc/nginx/sites-enabled/jobwindmark.bond.bootstrap.conf
# 去掉可能冲突的 default
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "==> 申请 / 续签 Let's Encrypt 证书"
CERT_ARGS=(-d "$DOMAIN")
APEX_IP="$(dig +short "$APEX" A | grep -E '^[0-9.]+$' | head -1 || true)"
if [[ "$APEX_IP" == "$MYIP" ]]; then
  CERT_ARGS+=(-d "$APEX")
fi
certbot certonly --webroot -w /var/www/certbot \
  --non-interactive --agree-tos --register-unsafely-without-email \
  --keep-until-expiring \
  "${CERT_ARGS[@]}"

# 探测证书目录名
CERT_DIR=""
for cand in "$DOMAIN" "$APEX"; do
  if [[ -f "/etc/letsencrypt/live/$cand/fullchain.pem" ]]; then
    CERT_DIR="$cand"
    break
  fi
done
if [[ -z "$CERT_DIR" ]]; then
  echo "错误：未找到证书目录 /etc/letsencrypt/live/{domain}/" >&2
  ls -la /etc/letsencrypt/live/ >&2 || true
  exit 1
fi
echo "    证书目录: /etc/letsencrypt/live/$CERT_DIR"

echo "==> 安装正式 HTTPS 站点配置"
cp "$LIMIT_SRC" /etc/nginx/conf.d/wind_agent_limit_req.conf
# 按实际证书目录改写 conf
sed "s|/etc/letsencrypt/live/www.jobwindmark.bond/|/etc/letsencrypt/live/${CERT_DIR}/|g" \
  "$CONF_SRC" > /etc/nginx/sites-available/jobwindmark.bond.conf
ln -sfn /etc/nginx/sites-available/jobwindmark.bond.conf /etc/nginx/sites-enabled/jobwindmark.bond.conf
rm -f /etc/nginx/sites-enabled/jobwindmark.bond.bootstrap.conf

nginx -t
systemctl reload nginx

echo "==> 公网应用改为仅 127.0.0.1（反代模式）"
# 同步最新代码并重启
WIND_BEHIND_PROXY=1 bash "$DEV_ROOT/scripts/sync_to_public.sh"

echo "==> 验收"
curl -fsS "http://127.0.0.1:8765/health" | head -c 200; echo
curl -fsSI "https://$DOMAIN/health" | head -20
curl -fsS "https://$DOMAIN/health" | head -c 200; echo

echo
echo "==> 完成。请确认云安全组已放行 80/443，并关闭对公网的 8765。"
echo "    访问：https://$DOMAIN/"
