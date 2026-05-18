/**
 * @vitest-environment jsdom
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { MoversTable } from "@/components/market/MoversTable";
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
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

describe("<MoversTable />", () => {
  test("空資料 → emptyText", async () => {
    mock.onGet("/market/movers").reply(200, { data: [] });
    wrap(<MoversTable type="gainers" market="TW" />);
    await waitFor(() => expect(screen.queryByText(/尚無資料/)).toBeInTheDocument());
  });

  test("有資料 → 顯示 symbol", async () => {
    mock.onGet("/market/movers").reply(200, {
      data: [
        { symbol: "2330", name: "台積電", close: "600", change_pct: "1.5" },
      ],
    });
    wrap(<MoversTable type="gainers" market="TW" />);
    await waitFor(() => expect(screen.queryByText("2330")).toBeInTheDocument());
    expect(screen.getByText("台積電")).toBeInTheDocument();
  });

  test("volume 模式時含成交量欄", async () => {
    mock.onGet("/market/movers").reply(200, {
      data: [{ symbol: "2317", name: "鴻海", close: "100", change_pct: "0", volume: 12345 }],
    });
    wrap(<MoversTable type="volume" market="TW" />);
    await waitFor(() => expect(screen.queryByText("2317")).toBeInTheDocument());
    expect(screen.getByText(/12,345|12345/)).toBeInTheDocument();
  });
});
