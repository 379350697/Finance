import { FormEvent, useState } from "react";
import { Send } from "lucide-react";
import { AskMessage, createAskSession, sendAskMessage } from "../api/client";

export function AskStockPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<AskMessage[]>([]);
  const [input, setInput] = useState("分析一下 000001");
  const [status, setStatus] = useState("待开始");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!input.trim()) return;

    setStatus("发送中");
    const activeSession =
      sessionId ?? (await createAskSession(input.slice(0, 20) || "问股会话")).id;
    setSessionId(activeSession);

    const response = await sendAskMessage(activeSession, input.trim());
    setMessages((current) => [...current, ...response.messages]);
    setInput("");
    setStatus("已回复");
  }

  return (
    <section className="tool-layout">
      <div className="tool-main">
        <header className="section-header">
          <div>
            <h2>问股</h2>
            <p>单 Agent</p>
          </div>
          <span className="status-pill">{status}</span>
        </header>

        <div className="chat-log" aria-live="polite">
          {messages.length === 0 ? (
            <div className="empty-state">输入股票代码开始分析。</div>
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
            placeholder="输入股票代码或问题"
          />
          <button aria-label="发送" title="发送" type="submit">
            <Send size={18} />
          </button>
        </form>
      </div>

      <aside className="context-panel">
        <h3>上下文</h3>
        <dl>
          <div>
            <dt>会话</dt>
            <dd>{sessionId ?? "未创建"}</dd>
          </div>
          <div>
            <dt>工具</dt>
            <dd>行情 / 快照 / 假盘 / 研报</dd>
          </div>
        </dl>
      </aside>
    </section>
  );
}
