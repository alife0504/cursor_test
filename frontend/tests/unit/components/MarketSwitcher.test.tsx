import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { MarketSwitcher } from "@/components/market/MarketSwitcher";

describe("<MarketSwitcher />", () => {
  test("選 TW 時 aria-selected", () => {
    render(<MarketSwitcher value="TW" onChange={() => {}} />);
    const tw = screen.getByRole("tab", { name: /台股/ });
    expect(tw.getAttribute("aria-selected")).toBe("true");
    const us = screen.getByRole("tab", { name: /美股/ });
    expect(us.getAttribute("aria-selected")).toBe("false");
  });

  test("點 US 觸發 onChange('US')", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<MarketSwitcher value="TW" onChange={onChange} />);
    await user.click(screen.getByRole("tab", { name: /美股/ }));
    expect(onChange).toHaveBeenCalledWith("US");
  });

  test("選 US 時切換 active", () => {
    render(<MarketSwitcher value="US" onChange={() => {}} />);
    expect(
      screen.getByRole("tab", { name: /美股/ }).getAttribute("aria-selected"),
    ).toBe("true");
  });
});
