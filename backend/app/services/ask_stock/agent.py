from app.services.llm.provider import LlmProvider, LlmProviderNotConfigured


class AskStockAgent:
    def __init__(self, tools, llm_provider: LlmProvider | None = None):
        self.tools = tools
        self.llm_provider = llm_provider

    def answer(self, query: str) -> str:
        quote_context = self.tools.get_quote_context(query)
        prompt = self._build_prompt(query=query, quote_context=quote_context)
        if self.llm_provider is not None:
            try:
                return self.llm_provider.generate(prompt)
            except (LlmProviderNotConfigured, RuntimeError):
                pass
        return (
            f"{quote_context}\n\n"
            "初步建议：先结合趋势、量能、策略快照和假盘收益连续观察；"
            "当前回答为单 Agent 工具上下文摘要，不构成真实投资建议。"
        )

    def _build_prompt(self, query: str, quote_context: str) -> str:
        return (
            "你是 A 股策略辅助工具的单 Agent 问股模块。"
            "请结合工具上下文回答用户问题，输出简洁建议和风险提示。\n"
            f"用户问题：{query}\n"
            f"工具上下文：{quote_context}\n"
        )
