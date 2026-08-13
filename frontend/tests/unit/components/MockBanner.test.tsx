import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { MockBanner } from "@/components/common/MockBanner";

describe("<MockBanner />", () => {
  test("預設標題含 Mock 與 v1.1", () => {
    render(<MockBanner />);
    const node = screen.getByTestId("mock-banner");
    expect(node).toBeInTheDocument();
    expect(node.textContent).toMatch(/Mock/);
    expect(node.textContent).toMatch(/v1\.1/);
  });

  test("自訂 title", () => {
    render(<MockBanner title="這是自訂標題" />);
    expect(screen.getByText("這是自訂標題")).toBeInTheDocument();
  });

  test("含 trackingRef 文字", () => {
    render(<MockBanner trackingRef="GH#123" />);
    expect(screen.getByText(/GH#123/)).toBeInTheDocument();
  });

  test("無 trackingRef 時不渲染追蹤", () => {
    render(<MockBanner />);
    expect(screen.queryByText(/追蹤:/)).toBeNull();
  });
});
