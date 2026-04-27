from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from app.core.config import settings
from app.services.llm.provider import LlmProvider, LlmProviderNotConfigured, OpenAICodexProvider


def build_fallback_daily_report(
    trade_date: str,
    candidates_count: int,
    orders_count: int,
    total_return_pct: float,
) -> str:
    direction = "正收益" if total_return_pct >= 0 else "回撤"
    return (
        f"{trade_date} 日研报\n\n"
        f"- 策略命中 {candidates_count} 只股票，生成模拟订单 {orders_count} 笔。\n"
        f"- 当日假盘总收益率 {total_return_pct:.2f}%，结果表现为{direction}。\n"
        "- 建议：继续记录命中原因、快照字段和收盘收益，观察连续性胜率。\n"
        "- 风险：当前为模拟交易结果，不代表真实成交；需警惕数据源延迟、涨跌停无法成交和市场系统性波动。"
    )


@dataclass
class ReportService:
    llm_provider: LlmProvider | None = None
    provider_name: str = field(default_factory=lambda: settings.llm_provider)
    model: str = field(default_factory=lambda: settings.llm_model)

    def generate_daily_report(
        self,
        trade_date: str,
        candidates_count: int,
        orders_count: int,
        total_return_pct: float,
    ) -> str:
        prompt = self._build_daily_prompt(
            trade_date=trade_date,
            candidates_count=candidates_count,
            orders_count=orders_count,
            total_return_pct=total_return_pct,
        )
        provider = self.llm_provider or OpenAICodexProvider()
        try:
            return provider.generate(prompt)
        except (LlmProviderNotConfigured, httpx.HTTPError, RuntimeError):
            return build_fallback_daily_report(
                trade_date=trade_date,
                candidates_count=candidates_count,
                orders_count=orders_count,
                total_return_pct=total_return_pct,
            )

    def _build_daily_prompt(
        self,
        trade_date: str,
        candidates_count: int,
        orders_count: int,
        total_return_pct: float,
    ) -> str:
        return (
            "你是 A 股策略辅助工具的单 Agent 研报分析模块。"
            "请基于策略候选、模拟订单和收益数据生成简洁日研报。\n"
            f"交易日：{trade_date}\n"
            f"候选股数量：{candidates_count}\n"
            f"模拟订单数量：{orders_count}\n"
            f"总收益率：{total_return_pct:.2f}%\n"
        )
