import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { MarketBadge } from "@/components/common/MarketBadge";

describe("<MarketBadge />", () => {
  test("TW 標籤", () => {
    render(<MarketBadge market="TW" />);
    expect(screen.getByText(/台股/)).toBeInTheDocument();
  });

  test("US 標籤", () => {
    render(<MarketBadge market="US" />);
    expect(screen.getByText(/美股/)).toBeInTheDocument();
  });
});
