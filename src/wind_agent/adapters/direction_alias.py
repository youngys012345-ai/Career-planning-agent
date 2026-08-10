"""方向模糊归一：把「agent算法工程师」等口语/前缀写法映射到规范方向与检索词。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# 规范方向 → 检索关键词（详情库 / 在线浅采）
DIRECTION_KEYWORDS: dict[str, list[str]] = {
    "数据分析": [
        "数据分析",
        "数据分析师",
        "商业分析",
        "BI",
        "数据挖掘",
        "数据运营",
        "数据科学家",
        "数据开发",
        "大数据",
    ],
    "产品经理": [
        "产品经理",
        "产品专员",
        "产品策划",
        "产品运营",
        "产品助理",
        "PM",
        "产品管理",
    ],
    "后端开发": [
        "后端",
        "服务端",
        "后台开发",
        "Java开发",
        "Java工程师",
        "Golang",
        "Go开发",
        "Python开发",
        "研发工程师JAVA",
        "研发工程师C/C++",
    ],
    "算法": [
        "算法工程师",
        "算法",
        "人工智能",
        "机器学习",
        "深度学习",
        "大模型",
        "NLP",
        "计算机视觉",
        "AI工程师",
        "AI算法",
    ],
    "前端开发": [
        "前端",
        "前端开发",
        "前端工程师",
        "Web前端",
        "React",
        "Vue",
        "H5",
    ],
    "测试": [
        "测试工程师",
        "测试开发",
        "质量保障",
        "QA",
        "自动化测试",
    ],
}

# 用于从口语中识别方向的别名（含规范名本身）；匹配时按长度降序
DIRECTION_ALIASES: dict[str, list[str]] = {
    "数据分析": [
        "数据分析师",
        "数据分析",
        "数据科学",
        "商业分析",
        "数据开发",
        "大数据工程",
        "BI工程师",
        "数据挖掘",
    ],
    "产品经理": [
        "产品经理",
        "产品管理",
        "产品专员",
        "产品策划",
        "产品助理",
        "产品运营",
    ],
    "后端开发": [
        "后端开发",
        "后端工程师",
        "服务端开发",
        "后台开发",
        "Java开发",
        "Go开发",
        "软件开发工程师",
    ],
    "算法": [
        "算法工程师",
        "算法岗",
        "算法",
        "人工智能工程师",
        "机器学习工程师",
        "深度学习工程师",
        "大模型算法",
        "AI算法工程师",
        "AI工程师",
        "NLP工程师",
        "计算机视觉工程师",
    ],
    "前端开发": [
        "前端开发",
        "前端工程师",
        "前端",
        "Web前端",
    ],
    "测试": [
        "测试开发",
        "测试工程师",
        "软件测试",
        "质量保障",
    ],
}

# 薪资库 / 供给库匹配 hints（与历史 _DIRECTION_HINTS 对齐并扩展）
DIRECTION_HINTS: dict[str, list[str]] = {
    "数据分析": ["数据分析", "数据科学", "商业分析", "数据开发", "大数据"],
    "产品经理": ["产品经理", "产品管理", "产品"],
    "后端开发": ["后端", "Java", "服务端", "软件开发"],
    "算法": ["算法", "人工智能", "机器学习", "深度学习", "大模型", "AI"],
    "前端开发": ["前端", "全栈", "Web"],
    "测试": ["测试", "质量保障", "QA"],
}

# 首页点选的规范方向（可被提问正文中的更具体岗位覆盖）
PRESET_DIRECTIONS: frozenset[str] = frozenset(
    {"数据分析", "产品经理", "后端开发", "算法", "前端开发", "测试"}
)

# 英文/符号噪声：常贴在岗位名前（agent算法工程师、AI产品经理）
_NOISE_TOKEN_RE = re.compile(
    r"(?i)(?:^|[\s\-_/·•])(?:agent|ai|aigc|llm|ml|nlp|cv|gpt|agi|sre|qa|pm)(?=[\s\-_/·•]|$|[\u4e00-\u9fff])"
)
# 紧贴中文的拉丁前缀（无分隔符）：agent算法 / AI产品
_GLUED_LATIN_PREFIX_RE = re.compile(
    r"(?i)^(?:agent|ai|aigc|llm|ml|nlp|cv|gpt|agi|sre|qa|pm)(?=[\u4e00-\u9fff])"
)
# 中文噪声前缀（智能体算法工程师）
_CN_NOISE_PREFIXES = ("智能体", "人工智能方向的", "人工智能方向")
_MULTI_SPACE_RE = re.compile(r"[\s\-_/·•]+")
# 中文岗位核心：连续汉字（含工程师/开发等）
_CN_CORE_RE = re.compile(r"[\u4e00-\u9fff]{2,20}")


@dataclass
class DirectionNorm:
    """方向归一结果。"""

    canonical: str = ""
    original: str = ""
    matched_alias: str = ""
    keywords: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    rewritten: bool = False

    def as_extras(self) -> dict[str, Any]:
        if not self.original and not self.canonical:
            return {}
        return {
            "direction_raw": self.original,
            "direction_canonical": self.canonical,
            "direction_matched_alias": self.matched_alias,
            "direction_rewritten": self.rewritten,
        }


def _alias_table() -> list[tuple[str, str]]:
    """(alias, canonical) 按 alias 长度降序。"""
    pairs: list[tuple[str, str]] = []
    for canonical, aliases in DIRECTION_ALIASES.items():
        for a in aliases:
            a = (a or "").strip()
            if a:
                pairs.append((a, canonical))
        pairs.append((canonical, canonical))
    # 去重保最长优先
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for a, c in sorted(pairs, key=lambda x: len(x[0]), reverse=True):
        key = a.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((a, c))
    return out


_ALIAS_PAIRS = _alias_table()


def strip_noise(text: str) -> str:
    """去掉 agent/AI 等英文前缀噪声，保留中文岗位核心。"""
    s = (text or "").strip()
    if not s:
        return ""
    prev = None
    while prev != s:
        prev = s
        s = _GLUED_LATIN_PREFIX_RE.sub("", s)
        s = _NOISE_TOKEN_RE.sub(" ", s)
        for pref in _CN_NOISE_PREFIXES:
            if s.startswith(pref) and len(s) > len(pref) + 1:
                s = s[len(pref) :]
        s = s.strip(" -\t_/·•")
    s = _MULTI_SPACE_RE.sub("", s)  # 中文场景去空白便于子串匹配
    return s


def text_mentions_canonical(text: str, canonical: str) -> bool:
    """提问是否提到该规范方向的任一别名。"""
    if not text or not canonical:
        return False
    aliases = list(DIRECTION_ALIASES.get(canonical) or []) + [canonical]
    for a in aliases:
        if a and (a in text or a.lower() in text.lower()):
            return True
    return False


def resolve_direction(user_text: str = "", direction: str = "") -> DirectionNorm:
    """综合方向框与提问正文，得到用于检索的规范方向。"""
    raw = (direction or "").strip()
    text = (user_text or "").strip()
    norm_dir = normalize_direction(raw) if raw else DirectionNorm()
    norm_text = extract_direction_from_text(text) if text else DirectionNorm()

    # 1) 方向框手填且命中别名（非单纯点选 chip）
    if raw and raw not in PRESET_DIRECTIONS and norm_dir.matched_alias:
        return norm_dir

    # 2) 正文抽到岗位，且点选 chip 未在正文出现 → 以正文为准（修复默认「数据分析」挡住算法提问）
    if norm_text.matched_alias:
        if not raw:
            return norm_text
        if raw in PRESET_DIRECTIONS and not text_mentions_canonical(text, norm_dir.canonical):
            return norm_text
        if (
            raw in PRESET_DIRECTIONS
            and norm_dir.canonical
            and norm_text.canonical != norm_dir.canonical
            and text_mentions_canonical(text, norm_text.canonical)
            and len(norm_text.matched_alias) >= 4
        ):
            # 正文明确写了另一岗位全称时覆盖 chip
            return norm_text

    # 3) 方向框规范结果
    if norm_dir.canonical:
        return norm_dir

    # 4) 仅正文
    if norm_text.canonical:
        return norm_text

    return DirectionNorm(original=raw or text)


def _match_alias_in_text(text: str) -> tuple[str, str] | None:
    """在文本中找最长别名，返回 (alias, canonical)。"""
    if not text:
        return None
    lower = text.lower()
    for alias, canonical in _ALIAS_PAIRS:
        if alias.lower() in lower or alias in text:
            return alias, canonical
    return None


def normalize_direction(raw: str) -> DirectionNorm:
    """将用户方向/手填岗位归一到规范方向。"""
    original = (raw or "").strip()
    if not original:
        return DirectionNorm()

    # 1) 原文直接命中别名
    hit = _match_alias_in_text(original)
    if hit:
        alias, canonical = hit
        return DirectionNorm(
            canonical=canonical,
            original=original,
            matched_alias=alias,
            keywords=list(DIRECTION_KEYWORDS.get(canonical) or [canonical]),
            hints=list(DIRECTION_HINTS.get(canonical) or [canonical]),
            rewritten=alias != original or canonical != original,
        )

    # 2) 去英文噪声后再匹配（agent算法工程师 → 算法工程师）
    cleaned = strip_noise(original)
    if cleaned and cleaned != original:
        hit = _match_alias_in_text(cleaned)
        if hit:
            alias, canonical = hit
            return DirectionNorm(
                canonical=canonical,
                original=original,
                matched_alias=alias,
                keywords=list(DIRECTION_KEYWORDS.get(canonical) or [canonical]),
                hints=list(DIRECTION_HINTS.get(canonical) or [canonical]),
                rewritten=True,
            )

    # 3) 抽取中文片段再匹配
    for frag in _CN_CORE_RE.findall(original):
        hit = _match_alias_in_text(frag)
        if hit:
            alias, canonical = hit
            return DirectionNorm(
                canonical=canonical,
                original=original,
                matched_alias=alias,
                keywords=list(DIRECTION_KEYWORDS.get(canonical) or [canonical]),
                hints=list(DIRECTION_HINTS.get(canonical) or [canonical]),
                rewritten=True,
            )

    # 4) 无法归一：保留原文，关键词用清洗后的中文核心 + 原文
    cores = _CN_CORE_RE.findall(cleaned or original)
    keywords = []
    for c in cores:
        if c not in keywords:
            keywords.append(c)
    if original not in keywords:
        keywords.insert(0, original)
    if cleaned and cleaned not in keywords:
        keywords.append(cleaned)
    return DirectionNorm(
        canonical=original,
        original=original,
        matched_alias="",
        keywords=keywords or [original],
        hints=[original],
        rewritten=False,
    )


def extract_direction_from_text(user_text: str) -> DirectionNorm:
    """从自然语言意愿中抽取方向。"""
    text = (user_text or "").strip()
    if not text:
        return DirectionNorm()
    # 先整段归一
    norm = normalize_direction(text)
    if norm.matched_alias:
        return norm
    # 再按别名表扫描（最长优先已在表中）
    hit = _match_alias_in_text(text)
    if hit:
        alias, canonical = hit
        return DirectionNorm(
            canonical=canonical,
            original=alias,
            matched_alias=alias,
            keywords=list(DIRECTION_KEYWORDS.get(canonical) or [canonical]),
            hints=list(DIRECTION_HINTS.get(canonical) or [canonical]),
            rewritten=True,
        )
    return DirectionNorm()


def direction_keywords(direction: str) -> list[str]:
    """供详情库过滤使用的关键词列表。"""
    norm = normalize_direction(direction)
    kws = list(norm.keywords or [])
    # 保证规范名也在列表中
    if norm.canonical and norm.canonical not in kws:
        kws.insert(0, norm.canonical)
    return kws


def direction_hints(direction: str) -> list[str]:
    """供薪资库 / 供给库打分使用的 hints。"""
    norm = normalize_direction(direction)
    hints = list(norm.hints or [])
    if norm.canonical and norm.canonical not in hints:
        hints.insert(0, norm.canonical)
    if norm.matched_alias and norm.matched_alias not in hints:
        hints.append(norm.matched_alias)
    return hints or ([direction] if direction else [])


def canonical_direction(direction: str) -> str:
    """仅返回规范方向字符串。"""
    return normalize_direction(direction).canonical or (direction or "").strip()
