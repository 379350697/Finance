import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import { App } from "./App";

describe("App", () => {
  test("renders main navigation", () => {
    render(<App />);

    expect(screen.getByText("问股")).toBeInTheDocument();
    expect(screen.getByText("策略模拟")).toBeInTheDocument();
    expect(screen.getByText("LLM 分析")).toBeInTheDocument();
  });
});
