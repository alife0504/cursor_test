import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { KpiCard } from "@/components/common/KpiCard";

describe("<KpiCard />", () => {
  test("title + value", () => {
    render(<KpiCard title="加權指數" value="22,000" />);
    expect(screen.getByText("加權指數")).toBeInTheDocument();
    expect(screen.getByText("22,000")).toBeInTheDocument();
  });

  test("delta 正值 → PriceDelta data-tone=bull", () => {
    const { container } = render(
      <KpiCard title="加權" value="22000" delta={1.2} />,
    );
    expect(container.querySelector('[data-tone="bull"]')).toBeTruthy();
  });

  test("onClick → button role + 點擊觸發", async () => {
    const onClick = vi.fn();
    render(<KpiCard title="A" value="1" onClick={onClick} />);
    await userEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledOnce();
  });

  test("Keyboard Enter 觸發 onClick", async () => {
    const onClick = vi.fn();
    render(<KpiCard title="A" value="1" onClick={onClick} />);
    const card = screen.getByRole("button");
    card.focus();
    await userEvent.keyboard("{Enter}");
    expect(onClick).toHaveBeenCalledOnce();
  });

  test("無 spark 不渲染 sparkline 容器", () => {
    const { container } = render(<KpiCard title="A" value="1" />);
    expect(container.querySelector('[data-testid="sparkline"]')).toBeNull();
  });
});
