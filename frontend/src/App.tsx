import { BarChart3, ChevronLeft, ChevronRight, FileText, LayoutDashboard, LogOut, Settings, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";
import { getOAuthStatus, logoutOAuth } from "./api/client";
import { LlmReportsPage } from "./pages/LlmReportsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { StrategyDashboardPage } from "./pages/StrategyDashboardPage";
import { StrategySimulationPage } from "./pages/StrategySimulationPage";
import { ThemeSwitcher } from "./components/ThemeSwitcher";

const tabs = [
  { id: "ask", label: "策略仪表盘", icon: LayoutDashboard },
  { id: "strategy", label: "策略模拟", icon: BarChart3 },
  { id: "reports", label: "LLM 分析", icon: FileText },
  { id: "settings", label: "设置", icon: Settings },
] as const;

type TabId = (typeof tabs)[number]["id"];

export function App() {
  const [activeTab, setActiveTab] = useState<TabId>("strategy");
  const [dashboardStrategy, setDashboardStrategy] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [oauthAuthed, setOauthAuthed] = useState(false);
  const [oauthChecking, setOauthChecking] = useState(true);

  useEffect(() => {
    getOAuthStatus()
      .then((s) => setOauthAuthed(s.authenticated))
      .catch(() => setOauthAuthed(false))
      .finally(() => setOauthChecking(false));
  }, []);

  const handleLogout = async () => {
    await logoutOAuth().catch(() => {});
    setOauthAuthed(false);
  };

  return (
    <main className={`app-shell${sidebarCollapsed ? " app-shell--collapsed" : ""}`}>
      <aside className={`sidebar${sidebarCollapsed ? " sidebar--collapsed" : ""}`}>
        <div className="sidebar-header">
          <h1>A 股策略助手</h1>
          <button
            className="sidebar-toggle"
            onClick={() => setSidebarCollapsed((v) => !v)}
            type="button"
            title={sidebarCollapsed ? "展开侧栏" : "收起侧栏"}
          >
            {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>
        <nav>
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                aria-current={activeTab === tab.id ? "page" : undefined}
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                type="button"
                title={sidebarCollapsed ? tab.label : undefined}
              >
                <Icon size={18} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        <ThemeSwitcher />

        <div className="oauth-control">
          {oauthChecking ? (
            <div className="oauth-btn" style={{ justifyContent: "center" }}>
              <span className="oauth-dot oauth-dot--gray" />
              <span style={{ fontSize: "12px" }}>检查授权...</span>
            </div>
          ) : oauthAuthed ? (
            <button className="oauth-btn" onClick={handleLogout} type="button" title="登出 OpenAI Codex">
              <LogOut size={14} />
              <span>已连接 · 登出</span>
              <span className="oauth-dot oauth-dot--green" />
            </button>
          ) : (
            <div className="oauth-btn" style={{ justifyContent: "center", cursor: "default" }}>
              <WifiOff size={14} />
              <span style={{ fontSize: "12px" }}>Codex 未登录</span>
            </div>
          )}
        </div>
      </aside>

      <section className="workspace">
        {activeTab === "ask" && (
          <StrategyDashboardPage
            onStrategyClick={(name) => {
              setDashboardStrategy(name);
              setActiveTab("strategy");
            }}
          />
        )}
        {activeTab === "strategy" && (
          <StrategySimulationPage
            initialStrategyName={dashboardStrategy}
            onStrategyNameConsumed={() => setDashboardStrategy(null)}
          />
        )}
        {activeTab === "reports" && <LlmReportsPage />}
        {activeTab === "settings" && <SettingsPage onOAuthChange={setOauthAuthed} />}
      </section>
    </main>
  );
}
