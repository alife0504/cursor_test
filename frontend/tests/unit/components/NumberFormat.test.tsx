import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { NumberFormat } from "@/components/common/NumberFormat";

describe("<NumberFormat />", () => {
  test("整數渲染千分位", () => {
    render(<NumberFormat value={1234567} />);
    expect(screen.getByText("1,234,567")).toBeInTheDocument();
  });

  test("decimal 字串保精度", () => {
    render(<NumberFormat value="98765.4321" decimals={2} />);
    expect(screen.getByText("98,765.43")).toBeInTheDocument();
  });

  test("null 顯示 fallback", () => {
    render(<NumberFormat value={null} fallback="N/A" />);
    expect(screen.getByText("N/A")).toBeInTheDocument();
  });

  test("undefined 顯示預設 fallback", () => {
    render(<NumberFormat value={undefined} />);
    expect(screen.getByText("-")).toBeInTheDocument();
  });

  test("空字串顯示 fallback", () => {
    render(<NumberFormat value="" />);
    expect(screen.getByText("-")).toBeInTheDocument();
  });

  test("套用 className", () => {
    const { container } = render(
      <NumberFormat value={100} className="text-red-500" />,
    );
    const span = container.querySelector("span");
    expect(span?.className).toContain("text-red-500");
    expect(span?.className).toContain("tabular-nums");
  });
});
