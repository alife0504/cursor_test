import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import {
  AnalystChooser,
  type AnalystType,
} from "@/components/analysis-new/AnalystChooser";

describe("<AnalystChooser />", () => {
  test("TW 顯示 5 個 analyst(含 sentiment 情緒 + chip 籌碼)", () => {
    render(<AnalystChooser value={[]} onChange={() => {}} market="TW" />);
    expect(screen.getByText(/Market/)).toBeInTheDocument();
    expect(screen.getByText(/Fundamental/)).toBeInTheDocument();
    expect(screen.getByText(/News/)).toBeInTheDocument();
    expect(screen.getByText(/Sentiment\(情緒\)/)).toBeInTheDocument();
    expect(screen.getByText(/Chip\(籌碼面\)/)).toBeInTheDocument();
  });

  test("US：情緒面與籌碼面皆顯示但禁用（不隱藏、標註原因）", () => {
    render(<AnalystChooser value={[]} onChange={() => {}} market="US" />);
    // 情緒面 + 籌碼面皆為台股專屬：美股時「顯示但禁用」，不讓選項憑空消失
    expect(screen.getByText(/Sentiment\(情緒\)/)).toBeInTheDocument();
    expect(screen.getByText(/Chip\(籌碼面\)/)).toBeInTheDocument();
    // 兩個 TW-only 分析師各自標註「美股不支援」徽章（只在 disabled 狀態渲染）
    expect(screen.getAllByText(/美股不支援/)).toHaveLength(2);
  });

  test("勾選時 onChange 被呼叫", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<AnalystChooser value={[]} onChange={onChange} market="TW" />);
    // 多個 label 指向同一 input(內外層 label),取第一個
    const labels = screen.getAllByLabelText(/Market\(技術面\)/);
    await user.click(labels[0]);
    expect(onChange).toHaveBeenCalledWith(["market"]);
  });

  test("已勾選後再點:取消勾選", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <AnalystChooser
        value={["market" as AnalystType]}
        onChange={onChange}
        market="TW"
      />,
    );
    const labels = screen.getAllByLabelText(/Market\(技術面\)/);
    await user.click(labels[0]);
    expect(onChange).toHaveBeenCalledWith([]);
  });
});
