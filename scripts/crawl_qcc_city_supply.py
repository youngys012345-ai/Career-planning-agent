#!/usr/bin/env python
"""企查查「地区岗位数排行」爬取 → qcc_city_supply_v0。

CDP 交互登录（不需要导出 Cookie）：
  1) 有图形界面：脚本自动打开 Chromium（远程调试端口）
  2) 无图形界面（云服务器）：在你自己电脑开 Chrome + ssh -R 反代
  3) 你在浏览器里手动登录企查查
  4) 回车后经 CDP（browser-use 探活 + Playwright 抽表）爬取类目

用法：
  .venv-crawl/bin/python scripts/crawl_qcc_city_supply.py --limit 2
  .venv-crawl/bin/python scripts/crawl_qcc_city_supply.py
  .venv-crawl/bin/python scripts/crawl_qcc_city_supply.py --cdp-url http://127.0.0.1:9222
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

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

from wind_agent.tools.metrics_real import normalize_city  # noqa: E402
from wind_agent.tools.supply_db import clear_cache, parse_city_rank_text  # noqa: E402

SALARY_PATH = ROOT / "data" / "snapshot" / "liepin_salary_v0" / "salaries.jsonl"
OUT_PATH = ROOT / "data" / "snapshot" / "qcc_city_supply_v0" / "supplies.jsonl"
DEBUG_DIR = ROOT / "data" / "reports" / "web" / "qcc_debug"
CITY_ALIASES = ROOT / "config" / "wind_agent" / "city_aliases.json"
PROFILE_DIR = ROOT / ".cache" / "qcc_cdp_profile"
QCC_HOME = "https://www.qcc.com/"
QCC_URL = "https://www.qcc.com/web/bigsearch/recruit?searchKey={key}"
DEFAULT_CDP_PORT = 9222


def _load_salary_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with SALARY_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def pick_search_key(row: dict[str, Any]) -> str:
    aliases = [str(a).strip() for a in (row.get("aliases") or []) if str(a).strip()]
    name = str(row.get("category_name") or "").strip()
    candidates = sorted(aliases, key=lambda s: (len(s), s)) if aliases else []
    for c in candidates:
        if 2 <= len(c) <= 12 and "与" not in c:
            return c
    if candidates:
        return candidates[0]
    name = re.split(r"[与/、]", name)[0].strip()
    return name or "招聘"


def _city_list() -> list[str]:
    if not CITY_ALIASES.is_file():
        return []
    data = json.loads(CITY_ALIASES.read_text(encoding="utf-8"))
    return list(data.get("cities") or [])


def normalize_cities(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cities = _city_list()
    merged: dict[str, int] = {}
    for item in raw:
        name = normalize_city(str(item.get("city") or ""), cities) or str(
            item.get("city") or ""
        ).replace("市", "").strip()
        if not name:
            continue
        try:
            cnt = int(item.get("job_count") or 0)
        except (TypeError, ValueError):
            cnt = 0
        if cnt <= 0:
            continue
        merged[name] = max(merged.get(name, 0), cnt)
    out = [{"city": k, "job_count": v} for k, v in merged.items()]
    out.sort(key=lambda x: (-x["job_count"], x["city"]))
    for i, c in enumerate(out, start=1):
        c["rank"] = i
    return out


def write_jsonl(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    clear_cache()
    ok = sum(1 for r in records if r.get("cities"))
    print(f"已写入 {path}：成功 {ok}/{len(records)} 条类目")


def _find_chrome() -> str:
    env = (os.getenv("CHROME_PATH") or "").strip()
    if env and Path(env).exists():
        return env
    # 优先 Playwright 完整 Chromium（比 snap 包装更适合 CDP）
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            exe = p.chromium.executable_path
            if exe and Path(exe).exists() and "headless" not in exe.lower():
                return exe
    except Exception:
        pass
    for name in (
        "google-chrome-stable",
        "google-chrome",
        "chromium",
        "chromium-browser",
        "chrome",
    ):
        p = shutil.which(name)
        if p and "snap" not in p:
            return p
        if p:
            return p
    raise SystemExit(
        "未找到 Chrome/Chromium。请设置 CHROME_PATH，"
        "或先执行：.venv-crawl/bin/playwright install chromium"
    )


def _cdp_ready(port: int, timeout: float = 40.0) -> str:
    """等待 Chrome 远程调试端口可用，返回 Playwright connect_over_cdp 地址。"""
    import urllib.request

    url = f"http://127.0.0.1:{port}/json/version"
    deadline = time.time() + timeout
    last_err = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                json.loads(resp.read().decode())
            return f"http://127.0.0.1:{port}"
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            time.sleep(0.4)
    raise RuntimeError(f"CDP 未就绪 :{port}（{last_err}）")


def _print_local_chrome_help(port: int) -> None:
    print(
        f"""
========== 请在你自己的电脑打开 Chrome（本机无图形界面）==========
Windows（PowerShell）示例：
  & \"$env:ProgramFiles\\Google\\Chrome\\Application\\chrome.exe\" `
    --remote-debugging-port={port} `
    --user-data-dir=\"$env:TEMP\\qcc-cdp-profile\" `
    https://www.qcc.com/

macOS：
  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\
    --remote-debugging-port={port} --user-data-dir=/tmp/qcc-cdp-profile https://www.qcc.com/

然后另开终端，把本机 {port} 反代到服务器（在你电脑执行）：
  ssh -R {port}:127.0.0.1:{port} 用户名@服务器

回到服务器，登录完成后按 Enter 继续；或直接：
  .venv-crawl/bin/python scripts/crawl_qcc_city_supply.py --cdp-url http://127.0.0.1:{port} --no-wait-login
================================================================
"""
    )


def launch_chrome_cdp(port: int, profile_dir: Path) -> subprocess.Popen | None:
    """启动带 CDP 的 Chromium（有界面），供手动登录。无 DISPLAY 时不启动，改为指引本机 Chrome。"""
    if not os.environ.get("DISPLAY"):
        _print_local_chrome_help(port)
        return None

    chrome = _find_chrome()
    profile_dir.mkdir(parents=True, exist_ok=True)
    args = [
        chrome,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
        "--new-window",
        QCC_HOME,
    ]
    print(f"启动浏览器 CDP={port}\n  {chrome}")
    return subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def wait_for_manual_login() -> None:
    print("\n========== 请手动登录企查查 ==========")
    print("1. 在弹出的浏览器中完成登录（验证码/扫码均可）")
    print("2. 确认能打开招聘大数据页后再继续")
    print("3. 回到本终端，按 Enter 开始爬取…")
    print("====================================\n")
    try:
        input()
    except EOFError:
        # 非交互环境：轮询等待一段时间（用户可另开终端附着）
        print("非交互终端：等待 120 秒供你登录…")
        time.sleep(120)


async def _extract_cities_from_page(page: Any, search_key: str) -> list[dict[str, Any]]:
    url = QCC_URL.format(key=quote(search_key))
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(2500)
    try:
        await page.wait_for_selector("text=地区", timeout=8000)
    except Exception:
        pass
    text = await page.inner_text("body")
    cities = normalize_cities(parse_city_rank_text(text))
    if len(cities) < 3:
        try:
            chunks = await page.eval_on_selector_all(
                "div, li, tr, span",
                """(nodes) => nodes.slice(0, 800).map(n => (n.innerText || '').trim()).filter(Boolean)""",
            )
            cities = normalize_cities(parse_city_rank_text("\n".join(chunks[:400])))
        except Exception:
            pass
    if len(cities) < 2:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", search_key)[:40]
        (DEBUG_DIR / f"{safe}.html").write_text(await page.content(), encoding="utf-8")
        try:
            await page.screenshot(path=str(DEBUG_DIR / f"{safe}.png"), full_page=True)
        except Exception:
            pass
        raise RuntimeError(f"未能解析地区岗位排行：{search_key}")
    return cities


async def crawl_via_cdp(
    cdp_http: str,
    rows: list[dict[str, Any]],
    *,
    limit: int | None,
    sleep_min: float,
    sleep_max: float,
    use_browser_use: bool,
) -> list[dict[str, Any]]:
    """经 CDP 附着已登录浏览器并爬取。"""
    targets = rows[: limit or len(rows)]
    out: list[dict[str, Any]] = []

    if use_browser_use:
        try:
            from browser_use import Browser  # type: ignore

            print(f"browser-use 经 CDP 附着：{cdp_http}")
            try:
                _bu = Browser(cdp_url=cdp_http)
            except TypeError:
                from browser_use import BrowserConfig  # type: ignore

                _bu = Browser(config=BrowserConfig(cdp_url=cdp_http))  # type: ignore
            print(f"browser-use Browser 已创建：{type(_bu).__name__}；表格抽取使用 Playwright CDP。")
        except ImportError:
            print("未安装 browser-use，仅用 Playwright CDP。")
        except Exception as exc:  # noqa: BLE001
            print(f"browser-use 初始化跳过：{exc}；继续 Playwright CDP。")

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_http)
        # 复用已有上下文，保留登录 Cookie
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()

        for idx, row in enumerate(targets, start=1):
            search_key = pick_search_key(row)
            print(f"[{idx}/{len(targets)}] {row.get('category_name')} ← {search_key}")
            errors: list[str] = []
            cities: list[dict[str, Any]] = []
            for attempt in range(1, 4):
                try:
                    cities = await _extract_cities_from_page(page, search_key)
                    break
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"attempt{attempt}: {exc}")
                    await page.wait_for_timeout(1200 * attempt)
            record = {
                "category_id": row.get("category_id"),
                "category_name": row.get("category_name"),
                "aliases": row.get("aliases") or [],
                "search_key": search_key,
                "source": "qcc_recruit",
                "url": QCC_URL.format(key=quote(search_key)),
                "crawled_at": datetime.now(timezone.utc).isoformat(),
                "cities": cities,
            }
            if errors and not cities:
                record["errors"] = errors
            out.append(record)
            await asyncio.sleep(random.uniform(sleep_min, sleep_max))

        # 不关闭用户浏览器，只断开 CDP 客户端
        await browser.close()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="企查查城市供给爬取（CDP 手动登录）")
    parser.add_argument(
        "--cdp-url",
        default=(os.getenv("CDP_URL") or "").strip() or None,
        help="已有浏览器的 CDP 地址，如 http://127.0.0.1:9222",
    )
    parser.add_argument("--cdp-port", type=int, default=DEFAULT_CDP_PORT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep-min", type=float, default=3.0)
    parser.add_argument("--sleep-max", type=float, default=8.0)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    parser.add_argument(
        "--no-browser-use",
        action="store_true",
        help="不探测 browser-use，仅用 Playwright CDP",
    )
    parser.add_argument(
        "--no-wait-login",
        action="store_true",
        help="跳过手动登录确认（检测到 CDP 后直接爬）",
    )
    args = parser.parse_args()

    if not SALARY_PATH.is_file():
        print(f"错误：找不到薪资库 {SALARY_PATH}", file=sys.stderr)
        return 2

    rows = _load_salary_rows()
    chrome_proc: subprocess.Popen | None = None
    cdp_http = args.cdp_url

    try:
        if not cdp_http:
            chrome_proc = launch_chrome_cdp(args.cdp_port, PROFILE_DIR)
            if chrome_proc is None:
                print(f"正在轮询 CDP http://127.0.0.1:{args.cdp_port} …")
                cdp_http = _cdp_ready(args.cdp_port, timeout=600)
                print(f"已检测到浏览器 CDP：{cdp_http}")
            else:
                cdp_http = _cdp_ready(args.cdp_port, timeout=40)
                print(f"CDP 就绪：{cdp_http}")
            if not args.no_wait_login:
                wait_for_manual_login()
            print(f"使用 CDP：{cdp_http}")
        else:
            print(f"附着已有 CDP：{cdp_http}")
            if not args.no_wait_login:
                wait_for_manual_login()

        records = asyncio.run(
            crawl_via_cdp(
                cdp_http,
                rows,
                limit=args.limit,
                sleep_min=args.sleep_min,
                sleep_max=args.sleep_max,
                use_browser_use=not args.no_browser_use,
            )
        )
        write_jsonl(records, args.out)
        return 0
    except KeyboardInterrupt:
        print("已中断")
        return 130
    finally:
        # 默认不杀浏览器，方便你复查；仅当我们拉起的进程且设置了 QCC_KILL_BROWSER=1 才关闭
        if chrome_proc and os.getenv("QCC_KILL_BROWSER", "").strip() in {"1", "true", "yes"}:
            try:
                os.killpg(chrome_proc.pid, signal.SIGTERM)
            except Exception:
                chrome_proc.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
