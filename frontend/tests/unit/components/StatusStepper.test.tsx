import { render } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { StatusStepper } from "@/components/common/StatusStepper";

function statesOf(container: HTMLElement) {
  return Array.from(container.querySelectorAll("li[data-state]")).map(
    (el) => el.getAttribute("data-state"),
  );
}

describe("<StatusStepper />", () => {
  test("queued → 第 1 步 running，其後 pending", () => {
    const { container } = render(<StatusStepper status="queued" />);
    expect(statesOf(container)).toEqual([
      "running",
      "pending",
      "pending",
      "pending",
      "pending",
    ]);
  });

  test("running 且 debate_count=2 → 第 3 步 active", () => {
    const { container } = render(
      <StatusStepper status="running" debateCount={2} />,
    );
    expect(statesOf(container)).toEqual([
      "done",
      "done",
      "running",
      "pending",
      "pending",
    ]);
  });

  test("completed → 全部 done", () => {
    const { container } = render(<StatusStepper status="completed" />);
    expect(statesOf(container)).toEqual([
      "done",
      "done",
      "done",
      "done",
      "done",
    ]);
  });

  test("failed running 階段 → 該步 state=failed", () => {
    const { container } = render(
      <StatusStepper status="failed" debateCount={2} />,
    );
    expect(statesOf(container)).toEqual([
      "done",
      "done",
      "failed",
      "pending",
      "pending",
    ]);
  });
});
