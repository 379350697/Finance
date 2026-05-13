import { Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { BrinsonResult, FactorAttributionResult } from "../api/client";

type Props = {
  brinson?: BrinsonResult | null;
  factor?: FactorAttributionResult | null;
  height?: number;
};

const COLORS = ["var(--color-up)", "var(--color-accent)", "var(--color-warn)", "var(--color-down)"];

function toChartData(effects: { name: string; value: number; pct: number }[], category: string) {
  return effects.map((e) => ({
    name: e.name,
    value: e.pct,
    rawValue: e.value,
    category,
  }));
}

export default function AttributionWaterfall({ brinson, factor, height = 280 }: Props) {
  if (!brinson && !factor) {
    return (
      <div style={{ color: "var(--text-tertiary)", textAlign: "center", padding: 24 }}>
        无归因数据
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gap: "var(--space-lg)" }}>
      {brinson && (
        <div>
          <h4 style={{
            fontFamily: "var(--font-display)",
            fontSize: "var(--font-size-md)",
            margin: "0 0 var(--space-sm) 0",
          }}>
            Brinson 归因
            <span style={{
              marginLeft: 12,
              fontSize: "var(--font-size-sm)",
              color: "var(--text-secondary)",
              fontFamily: "var(--font-mono)",
            }}>
              超额: {(brinson.total_excess * 100).toFixed(2)}%
            </span>
          </h4>

          <div className="metric-grid" style={{ gridTemplateColumns: "repeat(3, 1fr)", marginBottom: "var(--space-md)" }}>
            <MetricSummary label="配置效应" effects={brinson.allocation_effects} />
            <MetricSummary label="选择效应" effects={brinson.selection_effects} />
            <MetricSummary label="交互效应" effects={brinson.interaction_effects} />
          </div>

          <div style={{ height }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={[
                  ...toChartData(brinson.allocation_effects, "配置效应"),
                  ...toChartData(brinson.selection_effects, "选择效应"),
                  ...toChartData(brinson.interaction_effects, "交互效应"),
                ]}
                margin={{ top: 10, right: 10, left: 20, bottom: 10 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 10, fontFamily: "var(--font-mono)", fill: "var(--text-secondary)" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fontFamily: "var(--font-mono)", fill: "var(--text-secondary)" }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-card)",
                    fontFamily: "var(--font-mono)",
                    fontSize: "var(--font-size-sm)",
                  }}
                  formatter={(_: number, __: string, props: any) => [
                    `${props.payload.value?.toFixed(2)}%`,
                    `${props.payload.category} — ${props.payload.name}`,
                  ]}
                />
                <Legend
                  wrapperStyle={{ fontFamily: "var(--font-mono)", fontSize: "var(--font-size-xs)" }}
                />
                <Bar dataKey="value" name="贡献占比" radius={[4, 4, 0, 0]}>
                  {brinson.allocation_effects
                    .concat(brinson.selection_effects)
                    .concat(brinson.interaction_effects)
                    .map((entry, i) => (
                      <Cell key={i} fill={entry.value >= 0 ? "var(--color-up)" : "var(--color-down)"} />
                    ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {factor && (
        <div>
          <h4 style={{
            fontFamily: "var(--font-display)",
            fontSize: "var(--font-size-md)",
            margin: "0 0 var(--space-sm) 0",
          }}>
            因子归因
            <span style={{
              marginLeft: 12,
              fontSize: "var(--font-size-sm)",
              color: "var(--text-secondary)",
              fontFamily: "var(--font-mono)",
            }}>
              总收益: {(factor.total_return * 100).toFixed(2)}%
            </span>
          </h4>

          <div style={{ height }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={factor.factor_contributions.map((fc, i) => ({
                  name: fc.name,
                  contribution: fc.pct,
                  fill: COLORS[i % COLORS.length],
                }))}
                margin={{ top: 10, right: 10, left: 20, bottom: 10 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 10, fontFamily: "var(--font-mono)", fill: "var(--text-secondary)" }}
                  angle={-30}
                  textAnchor="end"
                  interval={0}
                  height={60}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fontFamily: "var(--font-mono)", fill: "var(--text-secondary)" }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-card)",
                    fontFamily: "var(--font-mono)",
                    fontSize: "var(--font-size-sm)",
                  }}
                  formatter={(value: number) => [`${value.toFixed(2)}%`, "贡献度"]}
                />
                <Bar dataKey="contribution" name="因子贡献" radius={[4, 4, 0, 0]}>
                  {factor.factor_contributions.map((entry, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {factor.residual && (
            <div style={{
              marginTop: "var(--space-sm)",
              padding: "8px 12px",
              borderRadius: "var(--radius-md)",
              background: "var(--bg-input)",
              fontFamily: "var(--font-mono)",
              fontSize: "var(--font-size-sm)",
              color: "var(--text-secondary)",
            }}>
              残差: {factor.residual.pct.toFixed(2)}% ({factor.residual.value >= 0 ? "+" : ""}
              {(factor.residual.value * 100).toFixed(2)}%)
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MetricSummary({
  label,
  effects,
}: {
  label: string;
  effects: { name: string; value: number; pct: number }[];
}) {
  const total = effects.reduce((sum, e) => sum + e.value, 0);
  return (
    <div className="metric">
      <span>{label}</span>
      <strong style={{ color: total >= 0 ? "var(--color-up)" : "var(--color-down)" }}>
        {(total * 100).toFixed(2)}%
      </strong>
    </div>
  );
}
