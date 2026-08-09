# 求职风向 Agent（Career Planning / Wind Agent）

校招 **Market-first** 求职风向 Agent：按意愿方向读市场能力要求与准备路线，结论可解释；百炼（DashScope）负责职责概括 / 准备计划 / 核心结论。

仓库：[youngys012345-ai/Career-planning-agent](https://github.com/youngys012345-ai/Career-planning-agent)

## 功能模块

1. 核心结论（风向判断）
2. 细分岗位与职责概括
3. 核心能力与专业要求（详情库词频）
4. 分城岗位供给（星级）
5. 预期薪资（猎聘薪资库 · 均数条形图）
6. 求职风向（**在线浅采**，合格 ≥3 才展示）
7. 能力准备计划（初/中/高）
8. 人在回路（改方向/城市后局部重算）

## 快速启动

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Windows: copy .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY
python scripts/serve_wind_agent.py
```

浏览器打开：http://127.0.0.1:8765/

CLI 出报告：

```bash
python scripts/run_wind_agent_demo.py \
  --query "我现在是大二统计专业学生，以后想找数据分析岗位工作，我应该如何准备。" \
  --direction 数据分析 \
  --out data/reports/demo_bailian.html
```

## 阿里云 ECS 部署（摘要）

1. 安全组放行 `8765`（或 80/443 + Nginx 反代）
2. `git clone https://github.com/youngys012345-ai/Career-planning-agent.git`
3. 安装依赖、配置 `.env`（`DASHSCOPE_API_KEY`）
4. 后台运行：

```bash
nohup python scripts/serve_wind_agent.py > wind_agent.log 2>&1 &
```

5. 公网体验：`http://<公网IP>:8765/`  
6. 将链接写入赛事提交文档（`docs/submission/` 在本地完整仓维护；本公开仓为部署精简版）

更细步骤见 [docs/DEPLOY.md](docs/DEPLOY.md)。

## 仓库包含（公网部署核心）

```text
src/wind_agent/          # Web + 编排 + 指标 + 在线浅采
config/wind_agent/       # 词典与词表
scripts/serve_wind_agent.py
scripts/run_wind_agent_demo.py
data/snapshot/campus985_v0/jobs.jsonl      # 详情库
data/snapshot/liepin_salary_v0/salaries.jsonl
requirements.txt
.env.example
```

## 技术栈

- FastAPI + uvicorn
- Jinja2 报告渲染
- DashScope / 通义（百炼）
- curl_cffi 在线浅采（智联公开搜索页）

## License

Apache-2.0
