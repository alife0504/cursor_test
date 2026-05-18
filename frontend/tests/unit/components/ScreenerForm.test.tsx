import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { ScreenerForm } from "@/components/screener/ScreenerForm";

describe("<ScreenerForm />", () => {
  const LS_KEY = "screener.lastFilters";

  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  test("送出時呼叫 onSubmit + 寫入 localStorage", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<ScreenerForm onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText(/PE 最大/), "15");
    await user.click(screen.getByRole("button", { name: /套用篩選/ }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const arg = onSubmit.mock.calls[0][0];
    expect(arg.PE_max).toBe(15);
    expect(arg.market).toBe("TW");

    const stored = window.localStorage.getItem(LS_KEY);
    expect(stored).not.toBeNull();
    expect(JSON.parse(stored!).PE_max).toBe(15);
  });

  test("空欄位 → null,非數字 → null", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<ScreenerForm onSubmit={onSubmit} />);
    await user.click(screen.getByRole("button", { name: /套用篩選/ }));
    const arg = onSubmit.mock.calls[0][0];
    expect(arg.PE_max).toBeNull();
    expect(arg.PE_min).toBeNull();
  });

  test("重置清空所有欄位", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<ScreenerForm onSubmit={onSubmit} />);
    await user.type(screen.getByLabelText(/PE 最小/), "5");
    await user.click(screen.getByRole("button", { name: /重置/ }));
    expect((screen.getByLabelText(/PE 最小/) as HTMLInputElement).value).toBe("");
  });

  test("initial 預填", () => {
    render(
      <ScreenerForm
        initial={{ market: "US", PE_max: 20, dividend_yield_min: 3 }}
        onSubmit={() => {}}
      />,
    );
    expect((screen.getByLabelText(/PE 最大/) as HTMLInputElement).value).toBe("20");
    expect((screen.getByLabelText(/殖利率/) as HTMLInputElement).value).toBe("3");
  });
});
