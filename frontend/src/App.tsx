import { BarChart3, FileText, LogIn, LogOut, MessageSquare } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { getOAuthStatus, logoutOAuth, startOAuth, postOAuthCallback } from "./api/client";
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
  const [oauthLoading, setOauthLoading] = useState(false);

  const refreshOAuthStatus = useCallback(() => {
    getOAuthStatus()
      .then((s) => setOauthAuthed(s.authenticated))
      .catch(() => setOauthAuthed(false));
  }, []);

  useEffect(() => {
    refreshOAuthStatus();
  }, [refreshOAuthStatus]);

  // Listen for OAuth callback messages from popup window.
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.data?.type === "oauth_callback") {
        const { code, state } = event.data;
        postOAuthCallback(code, state)
          .then(() => {
            setOauthAuthed(true);
            setOauthLoading(false);
          })
          .catch(() => setOauthLoading(false));
      }
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, []);

  const handleLogin = async () => {
    setOauthLoading(true);
    try {
      const { authorize_url } = await startOAuth();
      // Open the OpenAI authorization page in a popup.
      const popup = window.open(authorize_url, "openai_oauth", "width=600,height=700");
      if (!popup) {
        // Fallback: redirect current window if popup blocked.
        window.location.href = authorize_url;
      }
    } catch {
      setOauthLoading(false);
    }
  };

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
            <button
              type="button"
              className="oauth-btn oauth-btn--login"
              onClick={handleLogin}
              disabled={oauthLoading}
            >
              <LogIn size={16} />
              <span>{oauthLoading ? "跳转中…" : "OpenAI 登录"}</span>
            </button>
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

