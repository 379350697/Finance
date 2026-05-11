import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  computeFactors,
  FactorComputeResponse,
  FactorICData,
  getFactorICSummary,
  ICAnalysisSummary,
} from "../api/client";

type SortField = "name" | "ic_mean" | "ic_std" | "icir";
type SortDir = "asc" | "desc";

const factorSets = [
  { value: "alpha158", label: "Alpha158" },
  { value: "alpha360", label: "Alpha360" },
] as const;

export function FactorAnalysisPage() {
  const [factorSet, setFactorSet] = useState<string>("alpha158");
  const [codes, setCodes] = useState("000001,000002,600519");
  const [startDate, setStartDate] = useState("2024-01-01");
  const [endDate, setEndDate] = useState("2026-05-08");

  const [computeResult, setComputeResult] = useState<FactorComputeResponse | null>(null);
  const [icData, setIcData] = useState<(ICAnalysisSummary & { factor_ic: FactorICData[] }) | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [sortField, setSortField] = useState<SortField>("ic_mean");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const handleAnalyze = async () => {
    setLoading(true);
    setError(null);
    try {
      const codeList = codes
        .split(/[,，\s]+/)
        .map((c) => c.trim())
        .filter(Boolean);

      const [computeRes, icRes] = await Promise.all([
        computeFactors({
          codes: codeList,
          start_date: startDate,
          end_date: endDate,
          factor_set: factorSet,
        }).catch(() => null),
        getFactorICSummary(factorSet, codeList, startDate, endDate).catch(() => null),
      ]);

      setComputeResult(computeRes);
      setIcData(icRes);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "分析失败");
    } finally {
      setLoading(false);
    }
  };

  // Auto-run on first mount
  useEffect(() => {
    handleAnalyze();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sortedFactors = useMemo(() => {
    if (!icData?.factor_ic) return [];
    const list = [...icData.factor_ic];
    list.sort((a, b) => {
      let cmp: number;
      if (sortField === "name") {
        cmp = a.factor_name.localeCompare(b.factor_name);
      } else {
        cmp = (a[sortField] ?? 0) - (b[sortField] ?? 0);
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return list;
  }, [icData, sortField, sortDir]);

  const importanceData = useMemo(() => {
    if (!icData?.factor_ic) return [];
    return icData.factor_ic
      .map((f) => ({ name: f.factor_name, importance: Math.abs(f.ic_mean) }))
      .sort((a, b) => b.importance - a.importance)
      .slice(0, 20);
  }, [icData]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  };

  const formatIc = (val: number | undefined | null) => {
    if (val == null) return "--";
    return val.toFixed(4);
  };

  return (
    <section>
      {/* Section Header */}
      <div className="section-header page-enter">
        <div>
          <h2>因子分析</h2>
          <p>因子计算 · IC 分析 · 特征重要性</p>
        </div>
        {computeResult && (
          <span className="last-updated">
            {computeResult.codes_count} 只股票 · {computeResult.factor_count} 个因子
          </span>
        )}
      </div>

      {/* Controls */}
      <div className="action-row page-enter" style={{ flexWrap: "wrap" }}>
        <div className="segmented" style={{ marginBottom: 0 }}>
          {factorSets.map((fs) => (
            <button
              key={fs.value}
              type="button"
              aria-selected={factorSet === fs.value}
              onClick={() => setFactorSet(fs.value)}
            >
              {fs.label}
            </button>
          ))}
        </div>
        <label>
          代码
          <input
            value={codes}
            onChange={(e) => setCodes(e.target.value)}
            placeholder="逗号分隔"
            style={{ width: 200 }}
          />
        </label>
        <label>
          开始
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </label>
        <label>
          结束
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </label>
        <button type="button" onClick={handleAnalyze} disabled={loading}>
          {loading ? "分析中…" : "开始分析"}
        </button>
      </div>

      {error && (
        <div className="page-enter" style={{
          padding: "12px 16px",
          borderRadius: "var(--radius-md)",
          background: "var(--color-down-bg)",
          color: "var(--color-down)",
          fontSize: "var(--font-size-sm)",
          marginBottom: "var(--space-lg)",
        }}>
          {error}
        </div>
      )}

      {/* KPI Metric Grid */}
      {icData && (
        <div className="metric-grid page-enter">
          <div className="metric">
            <strong style={{ color: icData.ic_mean >= 0 ? "var(--color-up)" : "var(--color-down)" }}>
              {icData.ic_mean.toFixed(4)}
            </strong>
            <span>IC 均值</span>
          </div>
          <div className="metric">
            <strong style={{ color: icData.icir >= 0 ? "var(--color-up)" : "var(--color-down)" }}>
              {icData.icir.toFixed(4)}
            </strong>
            <span>ICIR</span>
          </div>
          <div className="metric">
            <strong style={{ color: icData.rank_ic_mean >= 0 ? "var(--color-up)" : "var(--color-down)" }}>
              {icData.rank_ic_mean.toFixed(4)}
            </strong>
            <span>Rank IC</span>
          </div>
          <div className="metric">
            <strong>
              {icData.factor_ic?.length ?? computeResult?.factor_count ?? "--"}
            </strong>
            <span>有效因子数</span>
          </div>
        </div>
      )}

      {/* Loading skeleton for KPI */}
      {loading && !icData && (
        <div className="metric-grid page-enter">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="metric">
              <div className="skeleton" style={{ width: 80, height: 22 }} />
              <div className="skeleton" style={{ width: 60, height: 10 }} />
            </div>
          ))}
        </div>
      )}

      {/* Charts Row */}
      {icData && (
        <div className="page-enter" style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
          gap: "var(--space-lg)",
          marginBottom: "var(--space-lg)",
        }}>
          {/* Feature Importance Bar Chart */}
          <div className="chart-card">
            <h3 style={{
              fontFamily: "var(--font-display)",
              fontSize: "var(--font-size-lg)",
              fontWeight: 700,
              margin: "0 0 var(--space-md) 0",
            }}>
              特征重要性 (Top 20 |IC|)
            </h3>
            <div style={{ height: 400 }}>
              {importanceData.length === 0 ? (
                <div style={{
                  display: "flex", alignItems: "center", justifyContent: "center",
                  height: "100%", color: "var(--text-tertiary)", flexDirection: "column", gap: "8px",
                }}>
                  <span>暂无特征重要性数据</span>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={importanceData}
                    layout="vertical"
                    margin={{ top: 0, right: 20, left: 100, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 11, fontFamily: "var(--font-mono)", fill: "var(--text-secondary)" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="name"
                      tick={{ fontSize: 11, fontFamily: "var(--font-mono)", fill: "var(--text-secondary)" }}
                      axisLine={false}
                      tickLine={false}
                      width={100}
                    />
                    <Tooltip
                      contentStyle={{
                        borderRadius: "var(--radius-md)",
                        border: "1px solid var(--border-color)",
                        background: "var(--bg-card)",
                        fontFamily: "var(--font-mono)",
                        fontSize: "var(--font-size-sm)",
                      }}
                      formatter={(value: number) => [value.toFixed(4), "|IC|"]}
                    />
                    <Bar dataKey="importance" fill="var(--color-accent)" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* IC Time Series */}
          <div className="chart-card">
            <h3 style={{
              fontFamily: "var(--font-display)",
              fontSize: "var(--font-size-lg)",
              fontWeight: 700,
              margin: "0 0 var(--space-md) 0",
            }}>
              IC 时序
            </h3>
            <div style={{ height: 400 }}>
              {icData.ic_series.length === 0 ? (
                <div style={{
                  display: "flex", alignItems: "center", justifyContent: "center",
                  height: "100%", color: "var(--text-tertiary)", flexDirection: "column", gap: "8px",
                }}>
                  <span>暂无 IC 时序数据</span>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={icData.ic_series} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10, fontFamily: "var(--font-mono)", fill: "var(--text-secondary)" }}
                      axisLine={false}
                      tickLine={false}
                      dy={8}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fontFamily: "var(--font-mono)", fill: "var(--text-secondary)" }}
                      axisLine={false}
                      tickLine={false}
                      domain={["auto", "auto"]}
                    />
                    <Tooltip
                      contentStyle={{
                        borderRadius: "var(--radius-md)",
                        border: "1px solid var(--border-color)",
                        background: "var(--bg-card)",
                        fontFamily: "var(--font-mono)",
                        fontSize: "var(--font-size-sm)",
                      }}
                    />
                    <Legend
                      wrapperStyle={{
                        fontFamily: "var(--font-mono)",
                        fontSize: "var(--font-size-xs)",
                        color: "var(--text-secondary)",
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="ic"
                      stroke="var(--color-up)"
                      strokeWidth={1.5}
                      dot={false}
                      name="IC"
                    />
                    <Line
                      type="monotone"
                      dataKey="rank_ic"
                      stroke="var(--color-accent)"
                      strokeWidth={1.5}
                      dot={false}
                      name="Rank IC"
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Factor List Table */}
      {sortedFactors.length > 0 && (
        <div className="table-wrap page-enter" style={{ marginBottom: "var(--space-lg)" }}>
          <h3 style={{
            fontFamily: "var(--font-display)",
            fontSize: "var(--font-size-lg)",
            fontWeight: 700,
            padding: "var(--space-md) var(--space-md) 0",
            color: "var(--text-secondary)",
          }}>
            因子列表
            <span style={{
              fontSize: "var(--font-size-sm)",
              fontWeight: 400,
              color: "var(--text-secondary)",
              marginLeft: "8px",
            }}>
              ({sortedFactors.length} 个)
            </span>
          </h3>
          <table>
            <thead>
              <tr>
                <th style={{ cursor: "pointer" }} onClick={() => handleSort("name")}>
                  因子名{sortField === "name" ? (sortDir === "asc" ? " ↑" : " ↓") : ""}
                </th>
                <th style={{ cursor: "pointer" }} onClick={() => handleSort("ic_mean")}>
                  IC 均值{sortField === "ic_mean" ? (sortDir === "asc" ? " ↑" : " ↓") : ""}
                </th>
                <th style={{ cursor: "pointer" }} onClick={() => handleSort("ic_std")}>
                  IC 标准差{sortField === "ic_std" ? (sortDir === "asc" ? " ↑" : " ↓") : ""}
                </th>
                <th style={{ cursor: "pointer" }} onClick={() => handleSort("icir")}>
                  ICIR{sortField === "icir" ? (sortDir === "asc" ? " ↑" : " ↓") : ""}
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedFactors.map((f) => (
                <tr key={f.factor_name}>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: "var(--font-size-sm)" }}>
                    {f.factor_name}
                  </td>
                  <td style={{
                    fontFamily: "var(--font-mono)",
                    color: f.ic_mean >= 0 ? "var(--color-up)" : "var(--color-down)",
                  }}>
                    {formatIc(f.ic_mean)}
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>
                    {formatIc(f.ic_std)}
                  </td>
                  <td style={{
                    fontFamily: "var(--font-mono)",
                    color: f.icir >= 0 ? "var(--color-up)" : "var(--color-down)",
                  }}>
                    {formatIc(f.icir)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty state when no data */}
      {!loading && !icData && !error && (
        <div className="empty-state page-enter">
          <span>暂无因子分析数据</span>
          <span className="empty-state-hint">请选择因子集、股票代码和日期范围，然后开始分析</span>
        </div>
      )}
    </section>
  );
}
