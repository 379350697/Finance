import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChevronDown, ChevronRight } from "lucide-react";
import {
  compareModels,
  listModels,
  ModelCompareItem,
  ModelCompareResponse,
  ModelTrainRequest,
  ModelTrainResult,
  trainModel,
} from "../api/client";

const factorSets = [
  { value: "alpha158", label: "Alpha158" },
  { value: "alpha360", label: "Alpha360" },
];

const modelTypes = [
  { value: "lightgbm", label: "LightGBM" },
  { value: "xgboost", label: "XGBoost" },
  { value: "catboost", label: "CatBoost" },
  { value: "mlp", label: "MLP" },
];

const labelTypes = [
  { value: "next_ret1", label: "下期收益 (1日)" },
  { value: "next_ret5", label: "下期收益 (5日)" },
  { value: "next_ret10", label: "下期收益 (10日)" },
  { value: "next_ret20", label: "下期收益 (20日)" },
];

const defaultHyperparams: Record<string, number> = {
  num_leaves: 31,
  learning_rate: 0.05,
  n_estimators: 100,
  max_depth: -1,
  min_child_samples: 20,
  subsample: 0.8,
  colsample_bytree: 0.8,
  reg_alpha: 0,
  reg_lambda: 0,
};

export function ModelTrainingPage() {
  // Form state
  const [modelName, setModelName] = useState("");
  const [factorSet, setFactorSet] = useState("alpha158");
  const [trainStart, setTrainStart] = useState("2024-01-01");
  const [trainEnd, setTrainEnd] = useState("2025-06-30");
  const [validStart, setValidStart] = useState("2025-07-01");
  const [validEnd, setValidEnd] = useState("2025-09-30");
  const [testStart, setTestStart] = useState("2025-10-01");
  const [testEnd, setTestEnd] = useState("2026-05-08");
  const [stockPool, setStockPool] = useState("");
  const [labelType, setLabelType] = useState("next_ret5");
  const [modelType, setModelType] = useState("lightgbm");
  const [hyperparams, setHyperparams] = useState<Record<string, number>>({ ...defaultHyperparams });
  const [showHyperparams, setShowHyperparams] = useState(false);

  // Training state
  const [training, setTraining] = useState(false);
  const [trainError, setTrainError] = useState<string | null>(null);
  const [trainResult, setTrainResult] = useState<ModelTrainResult | null>(null);

  // Comparison state
  const [comparing, setComparing] = useState(false);
  const [compareResult, setCompareResult] = useState<ModelCompareResponse | null>(null);
  const [compareError, setCompareError] = useState<string | null>(null);

  // Models list
  const [models, setModels] = useState<ModelTrainResult[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);

  const loadModels = async () => {
    setModelsLoading(true);
    try {
      const list = await listModels();
      setModels(list);
    } catch {
      // silent
    } finally {
      setModelsLoading(false);
    }
  };

  useEffect(() => {
    loadModels();
  }, []);

  const handleTrain = async () => {
    if (!modelName.trim()) {
      setTrainError("请输入模型名称");
      return;
    }

    setTraining(true);
    setTrainError(null);
    setTrainResult(null);

    try {
      const stockCodes = stockPool
        .split(/[,，\s]+/)
        .map((s) => s.trim())
        .filter(Boolean);

      const req: ModelTrainRequest = {
        model_name: modelName.trim(),
        factor_set: factorSet,
        train_start: trainStart,
        train_end: trainEnd,
        valid_start: validStart,
        valid_end: validEnd,
        test_start: testStart,
        test_end: testEnd,
        stock_pool: stockCodes,
        model_type: modelType,
        label_type: labelType,
        hyperparams,
      };

      const result = await trainModel(req);
      setTrainResult(result);
      // Refresh model list
      await loadModels();
    } catch (e: unknown) {
      setTrainError(e instanceof Error ? e.message : "训练失败");
    } finally {
      setTraining(false);
    }
  };

  const handleCompare = async () => {
    setComparing(true);
    setCompareError(null);
    setCompareResult(null);

    try {
      const stockCodes = stockPool
        .split(/[,，\s]+/)
        .map((s) => s.trim())
        .filter(Boolean);

      const result = await compareModels({
        model_name_prefix: modelName.trim() || "compare",
        factor_set: factorSet,
        train_start: trainStart,
        train_end: trainEnd,
        valid_start: validStart,
        valid_end: validEnd,
        test_start: testStart,
        test_end: testEnd,
        stock_pool: stockCodes,
        label_type: labelType,
        model_types: modelTypes.map((m) => m.value),
        hyperparams,
      });
      setCompareResult(result);
    } catch (e: unknown) {
      setCompareError(e instanceof Error ? e.message : "对比失败");
    } finally {
      setComparing(false);
    }
  };

  const updateHyperparam = (key: string, value: string) => {
    const num = parseFloat(value);
    if (!isNaN(num)) {
      setHyperparams((prev) => ({ ...prev, [key]: num }));
    }
  };

  const importanceData = trainResult?.feature_importance
    ? Object.entries(trainResult.feature_importance)
        .map(([name, importance]) => ({ name, importance: Math.abs(importance) }))
        .sort((a, b) => b.importance - a.importance)
        .slice(0, 20)
    : [];

  const formatIc = (val: number | undefined | null) => {
    if (val == null) return "--";
    return val.toFixed(4);
  };

  return (
    <section>
      {/* Section Header */}
      <div className="section-header page-enter">
        <div>
          <h2>模型训练</h2>
          <p>LightGBM 模型训练 · 因子集管理 · 特征重要性</p>
        </div>
      </div>

      {/* Training Form */}
      <div className="chart-card page-enter" style={{ marginBottom: "var(--space-lg)" }}>
        <h3 style={{
          fontFamily: "var(--font-display)",
          fontSize: "var(--font-size-lg)",
          fontWeight: 700,
          margin: "0 0 var(--space-md) 0",
        }}>
          训练配置
        </h3>

        <div style={{ display: "grid", gap: "var(--space-md)" }}>
          {/* Row 1: model name + factor set + label type */}
          <div style={{ display: "flex", gap: "var(--space-md)", flexWrap: "wrap", alignItems: "end" }}>
            <label style={{
              color: "var(--text-secondary)",
              fontFamily: "var(--font-mono)",
              fontSize: "var(--font-size-xs)",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.04em",
              display: "grid",
              gap: "6px",
            }}>
              模型名称
              <input
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                placeholder="例如: lightgbm_alpha158"
                style={{
                  minHeight: 38,
                  padding: "0 12px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-subtle)",
                  background: "var(--bg-input)",
                  fontSize: "var(--font-size-sm)",
                  fontFamily: "var(--font-mono)",
                  width: 220,
                }}
              />
            </label>

            <label style={{
              color: "var(--text-secondary)",
              fontFamily: "var(--font-mono)",
              fontSize: "var(--font-size-xs)",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.04em",
              display: "grid",
              gap: "6px",
            }}>
              因子集
              <select
                value={factorSet}
                onChange={(e) => setFactorSet(e.target.value)}
                style={{
                  minHeight: 38,
                  padding: "0 12px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-subtle)",
                  background: "var(--bg-input)",
                  fontSize: "var(--font-size-sm)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                {factorSets.map((fs) => (
                  <option key={fs.value} value={fs.value}>{fs.label}</option>
                ))}
              </select>
            </label>

            <label style={{
              color: "var(--text-secondary)",
              fontFamily: "var(--font-mono)",
              fontSize: "var(--font-size-xs)",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.04em",
              display: "grid",
              gap: "6px",
            }}>
              标签类型
              <select
                value={labelType}
                onChange={(e) => setLabelType(e.target.value)}
                style={{
                  minHeight: 38,
                  padding: "0 12px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-subtle)",
                  background: "var(--bg-input)",
                  fontSize: "var(--font-size-sm)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                {labelTypes.map((lt) => (
                  <option key={lt.value} value={lt.value}>{lt.label}</option>
                ))}
              </select>
            </label>

            <label style={{
              color: "var(--text-secondary)",
              fontFamily: "var(--font-mono)",
              fontSize: "var(--font-size-xs)",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.04em",
              display: "grid",
              gap: "6px",
            }}>
              模型类型
              <select
                value={modelType}
                onChange={(e) => setModelType(e.target.value)}
                style={{
                  minHeight: 38,
                  padding: "0 12px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-subtle)",
                  background: "var(--bg-input)",
                  fontSize: "var(--font-size-sm)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                {modelTypes.map((mt) => (
                  <option key={mt.value} value={mt.value}>{mt.label}</option>
                ))}
              </select>
            </label>
          </div>

          {/* Row 2: Date ranges */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
            gap: "var(--space-md)",
          }}>
            {([
              ["训练开始", trainStart, setTrainStart],
              ["训练结束", trainEnd, setTrainEnd],
              ["验证开始", validStart, setValidStart],
              ["验证结束", validEnd, setValidEnd],
              ["测试开始", testStart, setTestStart],
              ["测试结束", testEnd, setTestEnd],
            ] as const).map(([label, value, setter]) => (
              <label key={label} style={{
                color: "var(--text-secondary)",
                fontFamily: "var(--font-mono)",
                fontSize: "var(--font-size-xs)",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                display: "grid",
                gap: "6px",
              }}>
                {label}
                <input
                  type="date"
                  value={value}
                  onChange={(e) => setter(e.target.value)}
                  style={{
                    minHeight: 38,
                    padding: "0 12px",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--border-subtle)",
                    background: "var(--bg-input)",
                    fontSize: "var(--font-size-sm)",
                    fontFamily: "var(--font-mono)",
                  }}
                />
              </label>
            ))}
          </div>

          {/* Row 3: Stock pool */}
          <label style={{
            color: "var(--text-secondary)",
            fontFamily: "var(--font-mono)",
            fontSize: "var(--font-size-xs)",
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.04em",
            display: "grid",
            gap: "6px",
          }}>
            股票池 (逗号分隔，留空使用全部)
            <textarea
              value={stockPool}
              onChange={(e) => setStockPool(e.target.value)}
              placeholder="例如: 000001,000002,600519"
              rows={2}
              style={{
                padding: "8px 12px",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border-subtle)",
                background: "var(--bg-input)",
                fontSize: "var(--font-size-sm)",
                fontFamily: "var(--font-mono)",
                resize: "vertical",
              }}
            />
          </label>

          {/* Hyperparameters (collapsible) */}
          <div>
            <button
              type="button"
              onClick={() => setShowHyperparams((v) => !v)}
              style={{
                background: "transparent",
                border: "none",
                boxShadow: "none",
                color: "var(--text-secondary)",
                fontFamily: "var(--font-mono)",
                fontSize: "var(--font-size-xs)",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                padding: 0,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "4px",
                minHeight: "auto",
              }}
            >
              {showHyperparams ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              超参数 {showHyperparams ? "" : `(${Object.keys(hyperparams).length} 项)`}
            </button>
            {showHyperparams && (
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
                gap: "var(--space-md)",
                marginTop: "var(--space-md)",
                padding: "var(--space-md)",
                background: "var(--bg-input)",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border-subtle)",
              }}>
                {Object.entries(hyperparams).map(([key, value]) => (
                  <label key={key} style={{
                    color: "var(--text-secondary)",
                    fontFamily: "var(--font-mono)",
                    fontSize: "var(--font-size-xs)",
                    fontWeight: 600,
                    display: "grid",
                    gap: "4px",
                  }}>
                    {key}
                    <input
                      type="number"
                      value={value}
                      step={key === "learning_rate" ? "0.01" : key.includes("sample") ? "0.1" : "1"}
                      onChange={(e) => updateHyperparam(key, e.target.value)}
                      style={{
                        minHeight: 34,
                        padding: "0 8px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-subtle)",
                        background: "var(--bg-card)",
                        fontSize: "var(--font-size-sm)",
                        fontFamily: "var(--font-mono)",
                      }}
                    />
                  </label>
                ))}
              </div>
            )}
          </div>

          {/* Submit button */}
          <div style={{ display: "flex", gap: "var(--space-md)", alignItems: "center" }}>
            <button
              type="button"
              onClick={handleTrain}
              disabled={training}
              className="btn--primary"
              style={{ minHeight: 42, padding: "0 24px", fontWeight: 600 }}
            >
              {training ? "训练中…" : "开始训练"}
            </button>
            <button
              type="button"
              onClick={handleCompare}
              disabled={comparing}
              style={{ minHeight: 42, padding: "0 24px", fontWeight: 600 }}
            >
              {comparing ? "对比中…" : "对比全部模型"}
            </button>
            {trainError && (
              <span style={{
                color: "var(--color-down)",
                fontSize: "var(--font-size-sm)",
                fontFamily: "var(--font-mono)",
              }}>
                {trainError}
              </span>
            )}
            {compareError && (
              <span style={{
                color: "var(--color-down)",
                fontSize: "var(--font-size-sm)",
                fontFamily: "var(--font-mono)",
              }}>
                {compareError}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Training Results */}
      {trainResult && (
        <>
          {/* KPI Cards */}
          <div className="metric-grid page-enter">
            <div className="metric">
              <strong style={{ color: trainResult.ic_mean >= 0 ? "var(--color-up)" : "var(--color-down)" }}>
                {trainResult.ic_mean.toFixed(4)}
              </strong>
              <span>IC 均值</span>
            </div>
            <div className="metric">
              <strong style={{ color: trainResult.icir >= 0 ? "var(--color-up)" : "var(--color-down)" }}>
                {trainResult.icir.toFixed(4)}
              </strong>
              <span>ICIR</span>
            </div>
            <div className="metric">
              <strong style={{ color: trainResult.rank_icir >= 0 ? "var(--color-up)" : "var(--color-down)" }}>
                {trainResult.rank_icir.toFixed(4)}
              </strong>
              <span>Rank ICIR</span>
            </div>
            <div className="metric">
              <strong>{trainResult.mse.toFixed(4)}</strong>
              <span>MSE</span>
            </div>
          </div>

          {/* Feature Importance Chart */}
          {importanceData.length > 0 && (
            <div className="chart-card page-enter" style={{ marginBottom: "var(--space-lg)" }}>
              <h3 style={{
                fontFamily: "var(--font-display)",
                fontSize: "var(--font-size-lg)",
                fontWeight: 700,
                margin: "0 0 var(--space-md) 0",
              }}>
                特征重要性 (Top 20)
              </h3>
              <div style={{ height: 400 }}>
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
                      formatter={(value: number) => [value.toFixed(4), "重要性"]}
                    />
                    <Bar dataKey="importance" fill="var(--color-accent)" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </>
      )}

      {/* Trained Models List */}
      <div className="table-wrap page-enter" style={{ marginBottom: "var(--space-lg)" }}>
        <h3 style={{
          fontFamily: "var(--font-display)",
          fontSize: "var(--font-size-lg)",
          fontWeight: 700,
          padding: "var(--space-md) var(--space-md) 0",
          color: "var(--text-secondary)",
          display: "flex",
          alignItems: "center",
          gap: "var(--space-sm)",
        }}>
          已训练模型
          <button
            type="button"
            onClick={loadModels}
            disabled={modelsLoading}
            style={{
              minHeight: 28,
              padding: "0 8px",
              fontSize: "var(--font-size-xs)",
              marginLeft: "auto",
            }}
          >
            {modelsLoading ? "刷新中…" : "刷新"}
          </button>
        </h3>
        {models.length === 0 ? (
          <div className="empty-state">
            <span>暂无已训练模型</span>
            <span className="empty-state-hint">配置参数后点击「开始训练」创建模型</span>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>模型名称</th>
                <th>因子集</th>
                <th>IC 均值</th>
                <th>ICIR</th>
                <th>Rank ICIR</th>
                <th>MSE</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m) => (
                <tr
                  key={m.model_name}
                  style={
                    trainResult?.model_name === m.model_name
                      ? { background: "var(--bg-hover)" }
                      : undefined
                  }
                >
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: "var(--font-size-sm)", fontWeight: 600 }}>
                    {m.model_name}
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: "var(--font-size-xs)", color: "var(--text-secondary)" }}>
                    {m.factor_set}
                  </td>
                  <td style={{
                    fontFamily: "var(--font-mono)",
                    color: m.ic_mean >= 0 ? "var(--color-up)" : "var(--color-down)",
                  }}>
                    {formatIc(m.ic_mean)}
                  </td>
                  <td style={{
                    fontFamily: "var(--font-mono)",
                    color: m.icir >= 0 ? "var(--color-up)" : "var(--color-down)",
                  }}>
                    {formatIc(m.icir)}
                  </td>
                  <td style={{
                    fontFamily: "var(--font-mono)",
                    color: m.rank_icir >= 0 ? "var(--color-up)" : "var(--color-down)",
                  }}>
                    {formatIc(m.rank_icir)}
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>
                    {m.mse.toFixed(4)}
                  </td>
                  <td>
                    <span className={`status-badge ${m.status}`}>
                      {m.status === "completed" ? "已完成" : m.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Model Comparison Results */}
      {compareResult && (
        <div className="table-wrap page-enter" style={{ marginBottom: "var(--space-lg)" }}>
          <h3 style={{
            fontFamily: "var(--font-display)",
            fontSize: "var(--font-size-lg)",
            fontWeight: 700,
            padding: "var(--space-md) var(--space-md) 0",
            color: "var(--text-secondary)",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-sm)",
          }}>
            模型对比
            {compareResult.best_model && (
              <span style={{
                fontSize: "var(--font-size-xs)",
                fontWeight: 600,
                color: "var(--color-up)",
                fontFamily: "var(--font-mono)",
              }}>
                最佳: {compareResult.best_model}
              </span>
            )}
          </h3>
          <table>
            <thead>
              <tr>
                <th>模型类型</th>
                <th>IC 均值</th>
                <th>ICIR</th>
                <th>Rank IC</th>
                <th>Rank ICIR</th>
                <th>MSE</th>
                <th>训练耗时</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {compareResult.comparison.map((item) => {
                const isBest = item.model_type === compareResult.best_model;
                return (
                  <tr
                    key={item.model_type}
                    style={isBest ? { background: "var(--bg-hover)" } : undefined}
                  >
                    <td style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: "var(--font-size-sm)",
                      fontWeight: 600,
                      color: isBest ? "var(--color-up)" : undefined,
                    }}>
                      {item.model_type}
                      {isBest && " ★"}
                    </td>
                    <td style={{
                      fontFamily: "var(--font-mono)",
                      color: item.ic_mean >= 0 ? "var(--color-up)" : "var(--color-down)",
                    }}>
                      {formatIc(item.ic_mean)}
                    </td>
                    <td style={{
                      fontFamily: "var(--font-mono)",
                      color: item.icir >= 0 ? "var(--color-up)" : "var(--color-down)",
                    }}>
                      {formatIc(item.icir)}
                    </td>
                    <td style={{
                      fontFamily: "var(--font-mono)",
                      color: item.rank_ic_mean >= 0 ? "var(--color-up)" : "var(--color-down)",
                    }}>
                      {formatIc(item.rank_ic_mean)}
                    </td>
                    <td style={{
                      fontFamily: "var(--font-mono)",
                      color: item.rank_icir >= 0 ? "var(--color-up)" : "var(--color-down)",
                    }}>
                      {formatIc(item.rank_icir)}
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>
                      {item.mse.toFixed(4)}
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>
                      {item.train_time_seconds > 0 ? `${item.train_time_seconds.toFixed(1)}s` : "--"}
                    </td>
                    <td>
                      <span className={`status-badge ${item.status}`}>
                        {item.status === "completed" ? "已完成" : item.status}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
