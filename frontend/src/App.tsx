import { BarChart3, FileText, LogOut, MessageSquare, Settings, Terminal } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { getOAuthStatus, logoutOAuth, startDeviceAuth, pollDeviceAuth, DeviceAuthStartResult } from "./api/client";
import { AskStockPage } from "./pages/AskStockPage";
import { LlmReportsPage } from "./pages/LlmReportsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { StrategySimulationPage } from "./pages/StrategySimulationPage";

const tabs = [
  { id: "ask", label: "问股", icon: MessageSquare },
  { id: "strategy", label: "策略模拟", icon: BarChart3 },
  { id: "reports", label: "LLM 分析", icon: FileText },
  { id: "settings", label: "设置", icon: Settings },
] as const;

type TabId = (typeof tabs)[number]["id"];

export function App() {
  const [activeTab, setActiveTab] = useState<TabId>("strategy");

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
      </aside>
      <section className="workspace">
        {activeTab === "ask" && <AskStockPage />}
        {activeTab === "strategy" && <StrategySimulationPage />}
        {activeTab === "reports" && <LlmReportsPage />}
        {activeTab === "settings" && <SettingsPage />}
      </section>
    </main>
  );
}
