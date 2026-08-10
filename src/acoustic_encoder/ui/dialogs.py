"""Human-readable content for UI-owned explanatory dialogs and panels."""

from __future__ import annotations

from typing import Mapping


def format_unimplemented_message(details: Mapping[str, str]) -> str:
    return (
        f"该功能将在 {details['implementation_round']} 实现。\n"
        f"当前需要准备：{details['preparation']}\n"
        f"为什么暂时不能执行：{details['reason']}"
    )
