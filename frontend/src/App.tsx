import { BarChart3, FileText, MessageSquare } from "lucide-react";
import { useState } from "react";
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
      </section>
    </main>
  );
}
