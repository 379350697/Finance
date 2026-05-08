import { useEffect, useState } from "react";
import { FileText, RefreshCw } from "lucide-react";
import { Report, generateReport, listReports } from "../api/client";

const PERIODS = [
  { id: "daily", label: "日报" },
  { id: "weekly", label: "周报" },
  { id: "monthly", label: "月报" },
];

export function LlmReportsPage() {
  const [periodType, setPeriodType] = useState("daily");
  const [reports, setReports] = useState<Report[]>([]);
  const [selected, setSelected] = useState<Report | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");

  async function refresh() {
    try {
      const nextReports = await listReports();
      setReports(nextReports);
      setSelected((current) => current ?? nextReports[0] ?? null);
    } catch {}
  }

  async function handleGenerate() {
    setStatus("loading");
    try {
      const report = await generateReport(periodType, "2026-04-27", "2026-04-27");
      setReports((current) => [report, ...current]);
      setSelected(report);
      setStatus("done");
    } catch {
      setStatus("error");
    }
  }

  useEffect(() => {
    refresh().catch(() => setStatus("error"));
  }, []);

  const statusPillClass =
    status === "loading" ? "status-pill"
    : status === "error" ? "status-pill status-pill--error"
    : status === "idle" ? "status-pill status-pill--idle"
    : "status-pill";

  const statusText =
    status === "loading" ? "生成中…"
    : status === "error" ? "生成失败"
    : status === "idle" ? "待生成"
    : "已生成";

  return (
    <section className="tool-layout">
      <div className="tool-main">
        <header className="section-header">
          <div>
            <h2>LLM 分析</h2>
            <p>AI 驱动的研报生成 · openai_codex</p>
          </div>
          <span className={statusPillClass}>{statusText}</span>
        </header>

        <div className="segmented" role="tablist" aria-label="报告周期">
          {PERIODS.map((period) => (
            <button
              aria-selected={periodType === period.id}
              key={period.id}
              onClick={() => setPeriodType(period.id)}
              type="button"
            >
              {period.label}
            </button>
          ))}
        </div>

        <div className="action-row">
          <button title="生成报告" type="button" onClick={handleGenerate}>
            <FileText size={17} />
            <span>生成{PERIODS.find(p => p.id === periodType)?.label ?? "报告"}</span>
          </button>
          <button title="刷新" type="button" onClick={() => refresh()}>
            <RefreshCw size={17} />
          </button>
        </div>

        <article className="report-view">
          <h3>{selected?.title ?? "暂无报告"}</h3>
          <pre>{selected?.content ?? "点击上方「生成」按钮，AI 将根据最新的策略模拟结果和快照数据生成分析报告。"}</pre>
        </article>
      </div>

      <aside className="context-panel">
        <h3>报告列表</h3>
        <div className="report-list">
          {reports.length === 0 ? (
            <p style={{ color: "var(--text-tertiary)", textAlign: "center", padding: "20px 0" }}>
              暂无报告<br />
              <span style={{ fontSize: "var(--font-size-xs)" }}>生成第一份报告</span>
            </p>
          ) : (
            reports.map((report) => (
              <button
                key={report.id}
                onClick={() => setSelected(report)}
                type="button"
                aria-selected={selected?.id === report.id}
              >
                <span>{report.title}</span>
                <small>{report.period_type} · {report.provider}</small>
              </button>
            ))
          )}
        </div>
      </aside>
    </section>
  );
}
