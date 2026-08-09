"""工具注册表：名称 → 可调用实现。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., Any]
    parallel_group: str | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(
        self,
        name: str,
        description: str,
        handler: Callable[..., Any],
        parallel_group: str | None = None,
    ) -> None:
        self._tools[name] = ToolSpec(name, description, handler, parallel_group)

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"未注册工具: {name}")
        return self._tools[name]

    def call(self, name: str, **kwargs: Any) -> Any:
        return self.get(name).handler(**kwargs)

    def list_tools(self) -> list[dict[str, str | None]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parallel_group": t.parallel_group,
            }
            for t in self._tools.values()
        ]
