import { useEffect, useState } from "react";
import { FileText, RefreshCw } from "lucide-react";
import { Report, generateReport, listReports } from "../api/client";

const PERIODS = ["daily", "weekly", "monthly"];

export function LlmReportsPage() {
  const [periodType, setPeriodType] = useState("daily");
  const [reports, setReports] = useState<Report[]>([]);
  const [selected, setSelected] = useState<Report | null>(null);
  const [status, setStatus] = useState("待生成");

  async function refresh() {
    const nextReports = await listReports();
    setReports(nextReports);
    setSelected((current) => current ?? nextReports[0] ?? null);
  }

  async function handleGenerate() {
    setStatus("生成中");
    const report = await generateReport(periodType, "2026-04-27", "2026-04-27");
    setReports((current) => [report, ...current]);
    setSelected(report);
    setStatus("已生成");
  }

  useEffect(() => {
    refresh().catch(() => setStatus("连接失败"));
  }, []);

  return (
    <section className="tool-layout">
      <div className="tool-main">
        <header className="section-header">
          <div>
            <h2>LLM 分析</h2>
            <p>openai_codex</p>
          </div>
          <span className="status-pill">{status}</span>
        </header>

        <div className="segmented" role="tablist" aria-label="报告周期">
          {PERIODS.map((period) => (
            <button
              aria-selected={periodType === period}
              key={period}
              onClick={() => setPeriodType(period)}
              type="button"
            >
              {period}
            </button>
          ))}
        </div>

        <div className="action-row">
          <button title="生成报告" type="button" onClick={handleGenerate}>
            <FileText size={17} />
            <span>生成</span>
          </button>
          <button title="刷新" type="button" onClick={() => refresh()}>
            <RefreshCw size={17} />
          </button>
        </div>

        <article className="report-view">
          <h3>{selected?.title ?? "暂无报告"}</h3>
          <pre>{selected?.content ?? "生成后在这里查看研报内容。"}</pre>
        </article>
      </div>

      <aside className="context-panel">
        <h3>报告列表</h3>
        <div className="report-list">
          {reports.length === 0 ? (
            <p>暂无报告。</p>
          ) : (
            reports.map((report) => (
              <button key={report.id} onClick={() => setSelected(report)} type="button">
                <span>{report.title}</span>
                <small>{report.period_type}</small>
              </button>
            ))
          )}
        </div>
      </aside>
    </section>
  );
}
