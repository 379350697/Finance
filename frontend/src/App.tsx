import { BarChart3, FileText, LogOut, MessageSquare, Terminal } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { getOAuthStatus, logoutOAuth, startDeviceAuth, pollDeviceAuth, DeviceAuthStartResult } from "./api/client";
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
  const [deviceAuth, setDeviceAuth] = useState<DeviceAuthStartResult | null>(null);
  const [isStartingDeviceAuth, setIsStartingDeviceAuth] = useState(false);

  const refreshOAuthStatus = useCallback(() => {
    getOAuthStatus()
      .then((s) => {
        setOauthAuthed(s.authenticated);
        if (s.authenticated) {
          setDeviceAuth(null);
        }
      })
      .catch(() => setOauthAuthed(false));
  }, []);

  useEffect(() => {
    refreshOAuthStatus();
    const interval = setInterval(refreshOAuthStatus, 5000);
    return () => clearInterval(interval);
  }, [refreshOAuthStatus]);

  // Polling for device auth token
  useEffect(() => {
    if (!deviceAuth) return;

    const pollInterval = setInterval(() => {
      pollDeviceAuth(deviceAuth.device_auth_id, deviceAuth.user_code)
        .then((res) => {
          if (res.status === "authenticated") {
            setOauthAuthed(true);
            setDeviceAuth(null);
          }
        })
        .catch((err) => {
          console.error("Device auth poll error:", err);
        });
    }, deviceAuth.interval * 1000);

    return () => clearInterval(pollInterval);
  }, [deviceAuth]);

  const handleStartDeviceAuth = async () => {
    setIsStartingDeviceAuth(true);
    try {
      const res = await startDeviceAuth();
      setDeviceAuth(res);
    } catch (err) {
      console.error("Failed to start device auth:", err);
    } finally {
      setIsStartingDeviceAuth(false);
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
            <>
              <button
                type="button"
                className="oauth-btn oauth-btn--login"
                onClick={handleStartDeviceAuth}
                disabled={isStartingDeviceAuth || !!deviceAuth}
              >
                <Terminal size={16} />
                <span>{isStartingDeviceAuth ? "请求中..." : "OpenAI 登录"}</span>
              </button>
              {deviceAuth && (
                <div className="login-tip">
                  <p>1. 请在浏览器打开此链接：</p>
                  <a 
                    href={deviceAuth.verification_url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="login-tip-link"
                  >
                    {deviceAuth.verification_url}
                  </a>
                  <p>2. 输入以下一次性代码：</p>
                  <code>{deviceAuth.user_code}</code>
                  <p className="login-tip-sub">完成后将自动检测并登录</p>
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
