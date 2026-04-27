from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.ask import AskMessage, AskSession  # noqa: E402,F401
from app.models.paper_trading import PaperDailyReturn, PaperOrder, PaperPosition  # noqa: E402,F401
from app.models.report import LlmReport  # noqa: E402,F401
from app.models.snapshot import StockSnapshot  # noqa: E402,F401
from app.models.stock import Stock  # noqa: E402,F401
from app.models.strategy import StrategyCandidate, StrategyRun  # noqa: E402,F401
from app.models.task_run import TaskRun  # noqa: E402,F401
