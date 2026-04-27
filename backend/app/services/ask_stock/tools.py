import re

from app.services.data.provider import MarketDataError
from app.services.data.service import MarketDataService


class AskStockTools:
    def __init__(self, market_data: MarketDataService | None = None):
        self.market_data = market_data or MarketDataService()

    def get_quote_context(self, query: str) -> str:
        code = extract_stock_code(query)
        if not code:
            return "未识别到股票代码，请输入 6 位 A 股代码。"

        try:
            quote = self.market_data.get_quote(code)
        except MarketDataError as exc:
            return f"{code} 行情暂不可用：{exc}"

        parts = [f"{quote.code} {quote.name} 当前价 {quote.price:.2f}"]
        if quote.change_pct is not None:
            parts.append(f"涨跌幅 {quote.change_pct:.2f}%")
        if quote.volume is not None:
            parts.append(f"成交量 {quote.volume:.0f}")
        if quote.turnover is not None:
            parts.append(f"成交额 {quote.turnover:.0f}")
        return "，".join(parts)


def extract_stock_code(query: str) -> str | None:
    match = re.search(r"\b(\d{6})\b", query)
    return match.group(1) if match else None
