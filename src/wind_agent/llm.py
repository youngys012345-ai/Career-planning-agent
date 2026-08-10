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


def _strip_code_fence(text: str) -> str:
    text = (text or "").strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _balanced_json_slice(text: str, opener: str, closer: str) -> str | None:
    """从首个 opener 起做括号配平截取，避免 rfind 误吃内层数组。"""
    start = text.find(opener)
    if start < 0:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def extract_json_text(content: str) -> str:
    """从模型输出中抽出 JSON（去掉 ```json 围栏）。

    优先完整对象（如 {"conclusions":[...]}），避免先截到内层数组导致
    上层 `.get("conclusions")` 失败并落入数据分析向 stub。
    """
    import json as _json

    text = _strip_code_fence(content)
    if not text:
        return text
    try:
        _json.loads(text)
        return text
    except Exception:
        pass

    # 先试对象、再试数组；配平失败或非法 JSON 则换候选
    for opener, closer in (("{", "}"), ("[", "]")):
        snippet = _balanced_json_slice(text, opener, closer)
        if not snippet:
            continue
        try:
            _json.loads(snippet)
            return snippet
        except Exception:
            continue

    # 兜底：旧逻辑（首尾字符）
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
    return text
