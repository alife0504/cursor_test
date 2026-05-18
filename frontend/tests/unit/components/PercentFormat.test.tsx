import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { PercentFormat } from "@/components/common/PercentFormat";

describe("<PercentFormat />", () => {
  test("ratio 0.0825 → 8.25%", () => {
    render(<PercentFormat value={0.0825} />);
    expect(screen.getByText("8.25%")).toBeInTheDocument();
  });

  test("colored=true 正數紅色", () => {
    const { container } = render(
      <PercentFormat value={0.05} colored />,
    );
    const span = container.querySelector("span");
    expect(span?.className).toContain("text-green");
  });

  test("colored=true 負數綠色", () => {
    const { container } = render(<PercentFormat value={-0.05} colored />);
    const span = container.querySelector("span");
    expect(span?.className).toContain("text-red");
  });

  test("null fallback", () => {
    render(<PercentFormat value={null} fallback="—" />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
