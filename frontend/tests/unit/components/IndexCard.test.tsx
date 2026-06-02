import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { IndexCard } from "@/components/market/IndexCard";

describe("<IndexCard />", () => {
  test("顯示 name 與 value", () => {
    render(<IndexCard name="加權指數" value="17,000" changePct={1.23} />);
    expect(screen.getByText("加權指數")).toBeInTheDocument();
    expect(screen.getByText("17,000")).toBeInTheDocument();
  });

  test("正向漲跌幅顯示 + 號且 data-tone=bull（台股紅漲）", () => {
    const { container } = render(
      <IndexCard name="x" value="100" changePct={2.34} />,
    );
    expect(container.textContent ?? "").toMatch(/\+2\.34%/);
    expect(container.querySelector('[data-tone="bull"]')).toBeTruthy();
  });

  test("負向漲跌幅 data-tone=bear（台股綠跌）", () => {
    const { container } = render(
      <IndexCard name="x" value="100" changePct={-1.5} />,
    );
    expect(container.textContent ?? "").toMatch(/1\.50%/);
    expect(container.querySelector('[data-tone="bear"]')).toBeTruthy();
  });

  test("value 為 null 顯示 em dash", () => {
    render(<IndexCard name="x" value={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
