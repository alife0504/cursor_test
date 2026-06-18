/**
 * @vitest-environment jsdom
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { StockPicker } from "@/components/common/StockPicker";
import { api } from "@/lib/api";

let mock: MockAdapter;
beforeEach(() => {
  mock = new MockAdapter(api);
});
afterEach(() => mock.restore());

function wrap(node: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>{node}</QueryClientProvider>,
  );
}

describe("<StockPicker />", () => {
  test("inline 輸入框直接渲染（不需先點按鈕彈窗）", () => {
    wrap(<StockPicker onSelect={() => {}} />);
    // combobox 一開始就在 DOM、且是 <input>（原地輸入），而非藏在 trigger 按鈕後的浮層
    const box = screen.getByRole("combobox");
    expect(box).toBeInTheDocument();
    expect(box.tagName).toBe("INPUT");
  });

  test("輸入關鍵字 → 下方展開結果 → 點選回呼 onSelect", async () => {
    mock.onGet("/stocks").reply(200, {
      data: [
        { symbol: "2330", name: "台積電", market: "TWSE", is_active: true },
      ],
    });
    const onSelect = vi.fn();
    const user = userEvent.setup();
    wrap(<StockPicker onSelect={onSelect} />);

    await user.type(screen.getByRole("combobox"), "2330");

    const option = await screen.findByRole("option");
    expect(option).toHaveTextContent("2330");
    expect(option).toHaveTextContent("台積電");

    await user.click(option);
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ symbol: "2330" }),
    );
  });

  test("triggerLabel 已選狀態回填輸入框", () => {
    wrap(
      <StockPicker
        value="2454"
        triggerLabel="2454 聯發科"
        onSelect={() => {}}
      />,
    );
    expect(screen.getByRole("combobox")).toHaveValue("2454 聯發科");
  });
});
