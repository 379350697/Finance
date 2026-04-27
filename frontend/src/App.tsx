import { BarChart3, FileText, LogOut, MessageSquare, Terminal } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { getOAuthStatus, logoutOAuth } from "./api/client";
import { AskStockPage } from "./pages/AskStockPage";
import { LlmReportsPage } from "./pages/LlmReportsPage";
import { StrategySimulationPage } from "./pages/StrategySimulationPage";

const tabs = [
  { id: "ask", label: "问股", icon: MessageSquare },
  { id: "strategy", label: "策略模拟", icon: BarChart3 },
  { id: "reports", label: "LLM 分析", icon: FileText },
] as const;

type TabId = (typeof tabs)[number]["id"];

export function App() {
  const [activeTab, setActiveTab] = useState<TabId>("strategy");
  const [oauthAuthed, setOauthAuthed] = useState(false);
  const [showLoginTip, setShowLoginTip] = useState(false);

  const refreshOAuthStatus = useCallback(() => {
    getOAuthStatus()
      .then((s) => setOauthAuthed(s.authenticated))
      .catch(() => setOauthAuthed(false));
  }, []);

  useEffect(() => {
    refreshOAuthStatus();
    // Poll every 5s to pick up `codex login` results.
    const interval = setInterval(refreshOAuthStatus, 5000);
    return () => clearInterval(interval);
  }, [refreshOAuthStatus]);

  const handleLogout = async () => {
    await logoutOAuth().catch(() => {});
    setOauthAuthed(false);
  };

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <h1>A 股策略助手</h1>
        <nav>
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                aria-current={activeTab === tab.id ? "page" : undefined}
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                type="button"
              >
                <Icon size={18} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="oauth-control">
          {oauthAuthed ? (
            <button type="button" className="oauth-btn oauth-btn--logout" onClick={handleLogout}>
              <LogOut size={16} />
              <span>退出 OpenAI</span>
              <span className="oauth-dot oauth-dot--green" />
            </button>
          ) : (
            <>
              <button
                type="button"
                className="oauth-btn oauth-btn--login"
                onClick={() => setShowLoginTip(!showLoginTip)}
              >
                <Terminal size={16} />
                <span>OpenAI 登录</span>
              </button>
              {showLoginTip && (
                <div className="login-tip">
                  <p>在终端运行：</p>
                  <code>codex login</code>
                  <p className="login-tip-sub">登录后此处自动检测</p>
                </div>
              )}
            </>
          )}
        </div>
      </aside>
      <section className="workspace">
        {activeTab === "ask" && <AskStockPage />}
        {activeTab === "strategy" && <StrategySimulationPage />}
        {activeTab === "reports" && <LlmReportsPage />}
      </section>
    </main>
  );
}
