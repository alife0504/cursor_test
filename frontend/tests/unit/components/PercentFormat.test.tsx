import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { PercentFormat } from "@/components/common/PercentFormat";

describe("<PercentFormat />", () => {
  test("ratio 0.0825 → 8.25%", () => {
    render(<PercentFormat value={0.0825} />);
    expect(screen.getByText("8.25%")).toBeInTheDocument();
  });

  test("colored=true 正數 data-tone=bull（台股紅漲）", () => {
    const { container } = render(<PercentFormat value={0.05} colored />);
    const span = container.querySelector("span");
    expect(span?.getAttribute("data-tone")).toBe("bull");
    expect(span?.className).toContain("text-bull");
  });

  test("colored=true 負數 data-tone=bear（台股綠跌）", () => {
    const { container } = render(<PercentFormat value={-0.05} colored />);
    const span = container.querySelector("span");
    expect(span?.getAttribute("data-tone")).toBe("bear");
    expect(span?.className).toContain("text-bear");
  });

  test("null fallback", () => {
    render(<PercentFormat value={null} fallback="—" />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
