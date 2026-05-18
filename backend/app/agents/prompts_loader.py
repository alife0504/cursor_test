"""Prompt 模板讀取與渲染。

依 PLAN.md 第 18.2 章 Plugin Pattern + 第 20.3 章 Agent 輸出 schema 規範。

用法：
    from app.agents.prompts_loader import load_prompt, render_template
    sys_msg = load_prompt("market_analyst_system")
    usr_msg = render_template("market_analyst_user_tw_template",
                              symbol="2330", company_name="台積電", ...)

設計：
- 用 `importlib.resources` 讀 package 資源檔（適用 wheel / zip 部署）。
- render_template 使用 `str.format_map(SafeDict)` 避免缺 key 時整段炸掉
  （缺的 placeholder 會保留 `{key}` 字面，方便 debug；非生產阻塞）。
- LRU cache 避免重複讀 disk（template 不會 hot reload）。
"""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from typing import Any

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class _SafeDict(dict[str, Any]):
    """缺 key 時回 `{key}` 字面 — 不 raise KeyError。"""

    def __missing__(self, key: str) -> str:
        logger.warning("prompts.render.missing_key", key=key)
        return "{" + key + "}"


@lru_cache(maxsize=64)
def load_prompt(name: str) -> str:
    """讀取 `app.agents.prompts/<name>.txt` 的內容。

    Args:
        name: 不含 `.txt` 副檔名。如 "market_analyst_system"。

    Raises:
        FileNotFoundError: 模板不存在。
    """
    try:
        return (files("app.agents.prompts") / f"{name}.txt").read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error("prompts.load.not_found", name=name)
        raise


def render_template(name: str, /, **kwargs: Any) -> str:
    """讀取模板 + 用 kwargs 填空。

    缺 key 時保留 `{key}` 字面（不 raise）；caller 應在 logs 中觀察 missing_key 警告。
    """
    template = load_prompt(name)
    return template.format_map(_SafeDict(**kwargs))


__all__ = ["load_prompt", "render_template"]
