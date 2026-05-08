import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import { App } from "./App";
import { ThemeProvider } from "./ThemeContext";

describe("App", () => {
  test("renders main navigation", () => {
    render(
      <ThemeProvider>
        <App />
      </ThemeProvider>
    );

    expect(screen.getByText("问股")).toBeInTheDocument();
    expect(screen.getByText("策略模拟")).toBeInTheDocument();
    expect(screen.getByText("LLM 分析")).toBeInTheDocument();
  });
});
