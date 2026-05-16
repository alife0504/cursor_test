"""BaseAnalyst — Analyst Plugin 抽象基類 + Registry。

依 PLAN.md 第 18.2 章 Plugin Pattern。

設計：
- 每個 Analyst 子類設定 class-level metadata：
    name / display_name_zh / supported_regions / required_data_kinds
- 用 `@register_analyst` 裝飾器自動進 `ANALYST_REGISTRY`
- `analyze(state)` 接 `AgentState`，回 partial dict（langgraph 會 merge 回 state）
- `can_handle(region)` 由 graph_builder 過濾

P12 是 stub（只回固定字串）；P13 才接 LLM + Tool。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from app.core.logging_config import get_logger
from app.data_sources.base import DataKind, MarketRegion

if TYPE_CHECKING:
    from app.agents.state import AgentState
    from app.agents.tools import ToolRegistry
    from app.llm.base_provider import BaseLLMProvider

logger = get_logger(__name__)


# ── BaseAnalyst ─────────────────────────────────────────


class BaseAnalyst(ABC):
    """Analyst 的共同介面。

    子類規範：
    1. 設 `name`（registry key + state.analyses[name] 寫入 key）。
    2. 設 `display_name_zh`（前端顯示繁中名稱）。
    3. 設 `supported_regions`（TW / US / both）。
    4. 設 `required_data_kinds`（依賴的資料種類，graph_builder 可用來檢查資料源 ready）。
    5. Override `analyze(state)`：回 partial dict（至少含 `analyses[self.name]`）。

    P12 子類提供 stub `analyze`，P13 改為真實 LLM call。
    """

    # ── Subclass 必設 class attribute ─────────────────
    name: ClassVar[str] = "base"
    display_name_zh: ClassVar[str] = "基底分析師"
    supported_regions: ClassVar[list[MarketRegion]] = []
    required_data_kinds: ClassVar[list[DataKind]] = []

    def __init__(
        self,
        llm: BaseLLMProvider | None = None,
        tools: ToolRegistry | None = None,
    ) -> None:
        """注入 LLM + Tool registry。

        Args:
            llm: BaseLLMProvider 實例（P12 stub 可為 None）。
            tools: ToolRegistry 實例（P12 stub 可為 None）。
        """
        self.llm = llm
        self.tools = tools

    @abstractmethod
    async def analyze(self, state: AgentState) -> dict[str, Any]:
        """執行分析；回 partial state dict。

        Returns:
            dict like `{"analyses": {self.name: "分析內文..."}, ...}`，
            langgraph 會 merge 回 state（dict / list 欄位自動 reduce）。
        """
        ...

    def can_handle(self, region: MarketRegion | str) -> bool:
        """檢查本 Analyst 支援的市場區域。"""
        if isinstance(region, str):
            try:
                region = MarketRegion(region)
            except ValueError:
                return False
        return region in self.supported_regions

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{type(self).__name__} name={self.name!r} regions={self.supported_regions}>"


# ── ANALYST_REGISTRY ───────────────────────────────────

ANALYST_REGISTRY: dict[str, type[BaseAnalyst]] = {}


def register_analyst(cls: type[BaseAnalyst]) -> type[BaseAnalyst]:
    """類別裝飾器：自動把子類註冊進 `ANALYST_REGISTRY`。

    Usage::

        @register_analyst
        class MarketAnalyst(BaseAnalyst):
            name = "market"
            ...

    重複註冊同名 → 警告（後者覆蓋前者，方便測試環境替換）。
    """
    name = getattr(cls, "name", None)
    if not name or name == "base":
        raise ValueError(
            f"Analyst {cls.__name__} 必須設定 `name` class attribute（非空且不為 'base'）"
        )
    if name in ANALYST_REGISTRY and ANALYST_REGISTRY[name] is not cls:
        logger.warning(
            "analyst.register.duplicate",
            name=name,
            old=ANALYST_REGISTRY[name].__name__,
            new=cls.__name__,
        )
    ANALYST_REGISTRY[name] = cls
    logger.debug("analyst.registered", name=name, cls=cls.__name__)
    return cls


def get_analysts_for_region(
    region: MarketRegion | str,
    *,
    analyst_types: list[str] | None = None,
) -> list[type[BaseAnalyst]]:
    """取得支援指定區域的 Analyst class list。

    Args:
        region: 市場區域。
        analyst_types: 若給 → 額外過濾（只回 name 在此 list 的）；None → 全部支援的。

    Returns:
        Analyst class list（依 registry 註冊順序）。
    """
    if isinstance(region, str):
        try:
            region = MarketRegion(region)
        except ValueError as e:
            raise ValueError(f"未知 region: {region}") from e

    out: list[type[BaseAnalyst]] = []
    for name, cls in ANALYST_REGISTRY.items():
        if region not in cls.supported_regions:
            continue
        if analyst_types is not None and name not in analyst_types:
            continue
        out.append(cls)
    return out


__all__ = [
    "ANALYST_REGISTRY",
    "BaseAnalyst",
    "get_analysts_for_region",
    "register_analyst",
]
