from app.services.ask_stock.agent import AskStockAgent


class FakeTools:
    def get_quote_context(self, query: str) -> str:
        return "000001 当前价 10.50，涨跌幅 1.2%"


def test_ask_stock_agent_uses_tools_in_answer():
    agent = AskStockAgent(tools=FakeTools(), llm_provider=None)

    answer = agent.answer("分析一下 000001")

    assert "000001" in answer
    assert "当前价" in answer
