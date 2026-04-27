# A 股策略辅助工具设计

日期：2026-04-27

## 目标

搭建一个轻业务、可扩展的 A 股策略辅助工具。第一阶段先闭环核心流程：数据获取、策略筛选、个股快照、假盘模拟、收盘收益结算、LLM 日/周/月研报、单 Agent 问股。工程骨架预留 PostgreSQL、Redis、异步任务和前后端分层，后续可以自然扩展到更重的数据同步、任务调度和策略体系。

## 设计原则

- 业务先轻量闭环，不做复杂量化平台。
- 代码模块边界清晰，但后端不拆微服务。
- 所有策略结果必须可追溯：候选股、进场价格、快照、收益、研报都要入库。
- 问股只做单 Agent，不引入多 Agent 编排。
- 数据源统一封装，先可用，再逐步增强稳定性和覆盖面。

## 技术栈

- 后端：FastAPI
- 数据库：PostgreSQL
- 缓存与任务队列：Redis
- 异步任务：Celery
- 前端：React + Vite + TypeScript
- 本地编排：Docker Compose
- A 股数据源：AKShare 作为默认数据源，Tushare Pro 作为可选增强源，必要时用 efinance 做东方财富快速行情备选。

## 模块划分

### data

负责统一数据获取接口。第一版接入：

- A 股股票列表
- 实时行情
- 历史 K 线
- 个股基本信息
- 技术指标计算所需行情
- 可选资金流、财务、新闻数据

模块内部可以有多个 provider，例如 `akshare_provider`、`tushare_provider`、`efinance_provider`，对外只暴露统一的 `MarketDataService`。

### strategy

负责策略定义、参数管理和筛选执行。第一版内置少量基础策略，例如：

- 放量突破
- 均线趋势
- 低位反弹
- 自定义条件组合的预留接口

策略执行输出候选股列表，不直接修改持仓。候选股进入 snapshot 和 paper trading 流程。

### snapshot

负责保存每日策略命中的个股快照。快照尽量记录当时能拿到的信息：

- 股票代码、名称、交易日
- 最新价、开高低收、成交额、成交量、换手率、涨跌幅
- 关键技术指标
- 策略命中原因和策略参数
- 资金流、新闻摘要、基本面字段等可选信息

快照是后续复盘、LLM 研报和问股引用的核心证据。

### paper_trading

负责本地假盘：

- 根据策略命中结果模拟进场
- 记录订单、成交、持仓和收益
- 收盘后按收盘价或可配置价格结算
- 保存每日订单和收益曲线

第一版只做多头模拟，不做真实交易、不接券商、不做复杂撮合。

### llm

负责单 Agent 分析和报告生成：

- 日研报：基于当日策略命中、快照、模拟订单、收益和市场背景生成。
- 周研报：聚合一周策略效果、收益、胜率、典型个股和风险。
- 月研报：聚合月度表现、策略稳定性、参数建议和下月观察方向。

LLM 输出需要保存原始输入摘要、生成内容、建议、风险提示和创建时间。第一版默认按 `openai_codex` provider 接入，API Key、Base URL、模型名全部通过环境变量配置；代码层保留 provider 抽象，后续替换本地模型或其他供应商不影响策略、假盘和报告流程。如果 `openai_codex` 配置缺失，报告模块返回确定性的本地 fallback 内容，保证闭环不断。

### ask_stock

复刻 `daily_stock_analysis` 的问股核心体验，但只做单 Agent：

- 输入股票代码或自然语言问题
- Agent 可调用行情、K 线、技术指标、新闻、基本面、本地快照、假盘订单等工具
- 支持多轮上下文
- 支持查看分析过程摘要和最终建议

不做多 Agent 协作、不做复杂工作流图，避免第一版变重。

### scheduler / worker

负责异步任务和周期任务：

- 数据同步
- 策略筛选
- 快照生成
- 假盘进场
- 收盘结算
- 日/周/月研报生成

FastAPI 只负责触发和查询状态，耗时任务交给 Celery worker。

### web

前端保留三个核心板块：

- 问股：聊天式单 Agent 问股，旁边展示股票上下文。
- 策略模拟：选择策略、运行筛选、查看候选股、快照、订单和收益。
- LLM 分析：查看日研报、周研报、月研报，并能手动触发生成。

界面以简洁、工具型为主，不做营销式页面。

## 核心业务流程

1. 用户在前端选择策略并触发运行，或由定时任务自动运行。
2. 后端通过 data 模块获取行情和相关数据。
3. strategy 模块根据策略参数筛选股票。
4. snapshot 模块为命中的股票保存当日快照。
5. paper_trading 模块按规则创建模拟进场订单。
6. 收盘后 worker 触发结算，按收盘价计算收益并更新订单/持仓。
7. llm 模块读取当日快照、订单和收益，生成日研报。
8. 周期结束时聚合生成周研报和月研报。
9. ask_stock 模块可随时引用行情、本地快照、模拟交易和研报数据回答单股问题。

## 数据模型草案

- `stocks`：股票基础信息
- `market_bars`：历史行情
- `strategy_runs`：策略运行记录
- `strategy_candidates`：策略命中结果
- `stock_snapshots`：每日个股快照
- `paper_orders`：模拟订单
- `paper_positions`：模拟持仓
- `paper_daily_returns`：每日收益
- `llm_reports`：日/周/月研报
- `ask_sessions`：问股会话
- `ask_messages`：问股消息
- `task_runs`：异步任务状态

## API 设计草案

- `GET /health`
- `GET /api/stocks/search`
- `POST /api/strategies/run`
- `GET /api/strategies/runs`
- `GET /api/strategies/runs/{run_id}`
- `POST /api/paper-trading/settle`
- `GET /api/paper-trading/orders`
- `GET /api/paper-trading/returns`
- `POST /api/reports/generate`
- `GET /api/reports`
- `GET /api/reports/{report_id}`
- `POST /api/ask-stock/sessions`
- `POST /api/ask-stock/sessions/{session_id}/messages`
- `GET /api/tasks/{task_id}`

## 错误处理

- 数据源不可用时返回明确的 provider 错误，并记录失败原因。
- 异步任务失败写入 `task_runs`，前端展示失败状态和错误摘要。
- 策略运行必须保存输入参数，方便失败后重跑。
- LLM 调用失败不影响订单和收益数据，只标记报告生成失败。
- 外部 API 密钥缺失时，相关功能降级或提示配置缺失。

## 测试策略

- 单元测试：策略逻辑、指标计算、收益结算。
- 服务测试：数据 provider mock、快照生成、报告输入聚合。
- API 测试：策略运行、订单查询、问股消息、报告查询。
- 前端轻量测试：关键页面渲染和基础交互。
- 第一版以核心闭环可验证为主，不追求高覆盖率。

## 非目标

- 不接真实交易。
- 不做多 Agent。
- 不做实时高频行情。
- 不做复杂回测引擎。
- 不做完整券商风控和资金管理。

## 第一阶段交付

- 初始化前后端项目和 Docker Compose。
- 建立 PostgreSQL、Redis、Celery worker。
- 完成核心数据表和迁移。
- 接入 AKShare 基础数据。
- 实现一个可运行策略。
- 实现快照、模拟订单和收盘结算。
- 实现日研报生成接口。
- 实现单 Agent 问股基础聊天和工具调用。
- 前端完成问股、策略模拟、LLM 分析三个板块。
