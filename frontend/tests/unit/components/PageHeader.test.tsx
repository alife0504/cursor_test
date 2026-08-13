import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { PageHeader } from "@/components/common/PageHeader";

describe("<PageHeader />", () => {
  test("顯示 title 與 description", () => {
    render(<PageHeader title="儀表板" description="今日重點" />);
    expect(
      screen.getByRole("heading", { level: 1, name: "儀表板" }),
    ).toBeInTheDocument();
    expect(screen.getByText("今日重點")).toBeInTheDocument();
  });

  test("無 description 時不渲染 <p>", () => {
    const { container } = render(<PageHeader title="A" />);
    expect(container.querySelector("p")).toBeNull();
  });

  test("actions slot 渲染", () => {
    render(
      <PageHeader title="A" actions={<button type="button">行動</button>} />,
    );
    expect(screen.getByRole("button", { name: "行動" })).toBeInTheDocument();
  });
});
