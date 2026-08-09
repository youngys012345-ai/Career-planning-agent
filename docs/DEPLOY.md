# 公网部署说明（阿里云 ECS）

> 本文件用于服务器侧部署；提交赛事时把最终公网 URL 填进官网表单与使用手册。

## 1. 服务器准备

- 系统：Ubuntu 22.04 / Alibaba Cloud Linux 均可
- Python ≥ 3.10
- 安全组入方向：TCP `8765`（或 `80`/`443`）
- 建议安装：`git`、`python3-venv`、`nginx`（可选 HTTPS）

## 2. 拉取代码

```bash
cd /opt
sudo git clone https://github.com/youngys012345-ai/Career-planning-agent.git
cd Career-planning-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # 填入 DASHSCOPE_API_KEY
```

## 3. 启动服务

```bash
source .venv/bin/activate
nohup python scripts/serve_wind_agent.py > /var/log/wind_agent.log 2>&1 &
curl http://127.0.0.1:8765/health
```

公网访问：`http://<ECS公网IP>:8765/`

## 4. （可选）Nginx 反代 + HTTPS

```nginx
server {
    listen 80;
    server_name your.domain.com;
    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 5. 赛事提交

拿到公网链接后，填入：

- 大赛官网 / WeaveFox 提交表「体验链接」
- 作品使用手册中的公网地址栏

## 6. 注意

- **勿**把 `.env` 提交到 GitHub
- 在线浅采依赖服务器出网访问智联；若被拦截，报告中「求职风向」模块会按门禁隐藏
- 详情库与薪资库已随仓库附带精简快照，无需再跑采集脚本
