# 求职风向 Agent（Career Planning / Wind Agent）

校招 **Market-first** 求职风向 Agent：按意愿方向读市场能力要求与准备路线；百炼（DashScope）负责职责概括 / 准备计划 / 核心结论。

仓库：https://github.com/youngys012345-ai/Career-planning-agent

## 功能模块

1. 核心结论（风向判断）
2. 细分岗位与职责概括
3. 核心能力与专业要求（详情库词频）
4. 分城岗位供给（星级）
5. 预期薪资（猎聘薪资库 · 均数条形图）
6. 求职风向（在线浅采，合格 ≥3 才展示）
7. 能力准备计划（初/中/高）
8. 人在回路（改方向/城市后局部重算）

## 本地 / 云服务器启动

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY
python scripts/serve_wind_agent.py
```

- 本机：http://127.0.0.1:8765/
- 健康检查：http://127.0.0.1:8765/health

CLI 出报告：

```bash
python scripts/run_wind_agent_demo.py \
  --query "我现在是大二统计专业学生，以后想找数据分析岗位工作，我应该如何准备。" \
  --direction 数据分析 \
  --out data/reports/demo_bailian.html
```

## 阿里云 ECS 公网部署

1. 安全组入方向放行 **TCP 8765**（SSH 22 按需）
2. 克隆本仓库并安装：

```bash
cd /opt
git clone https://github.com/youngys012345-ai/Career-planning-agent.git
cd Career-planning-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env   # 填 DASHSCOPE_API_KEY
```

3. 后台启动：

```bash
nohup python scripts/serve_wind_agent.py > /var/log/wind_agent.log 2>&1 &
curl http://127.0.0.1:8765/health
```

4. 公网体验：`http://<公网IP>:8765/`（示例：`http://8.130.182.115:8765/`）

## 本仓库包含（仅部署核心）

```text
src/wind_agent/          # Web + 编排 + 指标 + 在线浅采
config/wind_agent/       # 词典与词表
scripts/serve_wind_agent.py
scripts/run_wind_agent_demo.py
data/snapshot/campus985_v0/jobs.jsonl
data/snapshot/liepin_salary_v0/salaries.jsonl
requirements.txt
.env.example
README.md
```

参赛文档、设计稿、采集脚本等**不在本仓库**，仅保留本地完整工作区。

## 技术栈

- FastAPI + uvicorn · Jinja2 · DashScope（qwen-plus）· curl_cffi

## License

Apache-2.0
