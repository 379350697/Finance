import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100vh",
          background: "#0a0a0f",
          color: "#e8e8ed",
          fontFamily: "monospace",
          padding: "40px",
        }}>
          <div style={{ maxWidth: "600px" }}>
            <h1 style={{ color: "#ff4455", marginBottom: "16px" }}>应用加载错误</h1>
            <pre style={{
              background: "#12121a",
              padding: "16px",
              borderRadius: "8px",
              overflow: "auto",
              whiteSpace: "pre-wrap",
              fontSize: "13px",
              lineHeight: 1.6,
              border: "1px solid #1e1e2c",
            }}>
              {this.state.error?.message}
              {"\n\n"}
              {this.state.error?.stack}
            </pre>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              style={{
                marginTop: "16px",
                padding: "8px 16px",
                background: "#ff4455",
                color: "#fff",
                border: "none",
                borderRadius: "6px",
                cursor: "pointer",
                fontSize: "14px",
              }}
            >
              重试
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
