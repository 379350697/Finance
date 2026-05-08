import { FormEvent, useState } from "react";
import { Send, Sparkles } from "lucide-react";
import { AskMessage, createAskSession, sendAskMessage } from "../api/client";

export function AskStockPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<AskMessage[]>([]);
  const [input, setInput] = useState("分析一下 000001");
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!input.trim()) return;

    setStatus("loading");
    try {
      const activeSession =
        sessionId ?? (await createAskSession(input.slice(0, 20) || "问股会话")).id;
      setSessionId(activeSession);

      const response = await sendAskMessage(activeSession, input.trim());
      setMessages((current) => [...current, ...response.messages]);
      setInput("");
      setStatus("done");
    } catch {
      setStatus("error");
    }
  }

  const statusPillClass =
    status === "loading" ? "status-pill"
    : status === "error" ? "status-pill status-pill--error"
    : status === "idle" ? "status-pill status-pill--idle"
    : "status-pill";

  const statusText =
    status === "loading" ? "分析中…"
    : status === "error" ? "请求失败"
    : status === "idle" ? "待提问"
    : "已回复";

  return (
    <section className="tool-layout">
      <div className="tool-main">
        <header className="section-header">
          <div>
            <h2>问股</h2>
            <p>AI 驱动的单股深度分析</p>
          </div>
          <span className={statusPillClass}>{statusText}</span>
        </header>

        <div className="chat-log" aria-live="polite">
          {messages.length === 0 ? (
            <div className="empty-state">
              <Sparkles size={28} style={{ margin: "0 auto", opacity: 0.3 }} />
              <span>输入股票代码或问题开始分析</span>
              <span className="empty-state-hint">支持：行情查询、技术分析、基本面评估</span>
            </div>
          ) : (
            messages.map((message) => (
              <article className={`message ${message.role}`} key={message.id}>
                <span>{message.role === "user" ? "你" : "Agent"}</span>
                <p>{message.content}</p>
              </article>
            ))
          )}
        </div>

        <form className="composer" onSubmit={handleSubmit}>
          <input
            aria-label="问股问题"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="输入股票代码或问题，如：分析一下 000001 的走势"
            disabled={status === "loading"}
          />
          <button aria-label="发送" title="发送" type="submit" disabled={status === "loading"}>
            <Send size={18} />
          </button>
        </form>
      </div>

      <aside className="context-panel">
        <h3>会话信息</h3>
        <dl>
          <div>
            <dt>会话 ID</dt>
            <dd>{sessionId ? sessionId.slice(0, 12) + "…" : "未创建"}</dd>
          </div>
          <div>
            <dt>消息数</dt>
            <dd>{messages.length}</dd>
          </div>
          <div>
            <dt>可用工具</dt>
            <dd>实时行情 · 快照 · 假盘 · 研报</dd>
          </div>
          <div>
            <dt>模型</dt>
            <dd>openai_codex</dd>
          </div>
        </dl>
      </aside>
    </section>
  );
}
