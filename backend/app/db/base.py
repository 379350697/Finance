from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def import_models() -> None:
    from app.models.ask import AskMessage, AskSession  # noqa: F401
    from app.models.paper_trading import PaperAccount, PaperDailyReturn, PaperOrder, PaperPosition, PaperSession  # noqa: F401
    from app.models.report import LlmReport  # noqa: F401
    from app.models.snapshot import StockSnapshot  # noqa: F401
    from app.models.stock import Stock  # noqa: F401
    from app.models.factor import FactorCache, ModelConfig  # noqa: F401
    from app.models.strategy import StrategyCandidate, StrategyRun  # noqa: F401
    from app.models.task_run import TaskRun  # noqa: F401
