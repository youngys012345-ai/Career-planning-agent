"""Evidence Pack：工具间共享契约；LLM 不得改写 metrics 数值。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class QueryPlan:
    direction: str = ""
    cities: list[str] = field(default_factory=lambda: ["全国主要城"])
    user_query: str = ""
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidencePack:
    query_plan: QueryPlan = field(default_factory=QueryPlan)
    metrics: dict[str, Any] = field(default_factory=dict)
    roles: dict[str, Any] = field(default_factory=dict)
    online: dict[str, Any] = field(default_factory=dict)
    generated: dict[str, Any] = field(default_factory=dict)
    flags: dict[str, bool] = field(
        default_factory=lambda: {
            "show_m6": False,
            "show_m9": False,
            "show_m11": False,
            "is_mock": True,
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvidencePack":
        qp = data.get("query_plan") or {}
        return cls(
            query_plan=QueryPlan(
                direction=qp.get("direction") or "",
                cities=list(qp.get("cities") or ["全国主要城"]),
                user_query=qp.get("user_query") or "",
                extras=dict(qp.get("extras") or {}),
            ),
            metrics=dict(data.get("metrics") or {}),
            roles=dict(data.get("roles") or {}),
            online=dict(data.get("online") or {}),
            generated=dict(data.get("generated") or {}),
            flags=dict(data.get("flags") or {}),
        )
