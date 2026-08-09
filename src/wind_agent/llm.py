"""百炼 / DashScope OpenAI 兼容客户端。"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]

_DEFAULT_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DEFAULT_MODEL = "qwen-plus"


def _ensure_env() -> None:
    if load_dotenv is not None:
        load_dotenv()


@lru_cache(maxsize=1)
def get_model() -> str:
    _ensure_env()
    return os.getenv("BAILIAN_MODEL") or _DEFAULT_MODEL


def get_api_key() -> str | None:
    _ensure_env()
    key = (os.getenv("DASHSCOPE_API_KEY") or "").strip()
    return key or None


def is_available() -> bool:
    return get_api_key() is not None


def get_client() -> Any | None:
    """返回 OpenAI 兼容客户端；无 key 时 None。"""
    api_key = get_api_key()
    if not api_key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None
    base_url = (os.getenv("OPENAI_BASE_URL") or _DEFAULT_BASE).strip()
    return OpenAI(api_key=api_key, base_url=base_url)


def chat(messages: list[dict[str, str]], *, temperature: float = 0.3) -> str | None:
    """调用 chat.completions；失败或无 key 返回 None。"""
    client = get_client()
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=get_model(),
            messages=messages,
            temperature=temperature,
        )
        content = resp.choices[0].message.content
        return (content or "").strip() or None
    except Exception:
        return None


def extract_json_text(content: str) -> str:
    """从模型输出中抽出 JSON（去掉 ```json 围栏）。"""
    text = (content or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # 去掉首尾围栏行
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    # 尝试截取首个 [ 或 { 到末尾匹配
    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
    return text
