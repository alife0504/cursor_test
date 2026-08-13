/**
 * @vitest-environment jsdom
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { useMyQuota } from "@/hooks/useQuota";
import { api } from "@/lib/api";

let mock: MockAdapter;

beforeEach(() => {
  mock = new MockAdapter(api);
});

afterEach(() => mock.restore());

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function W({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe("useMyQuota", () => {
  test("回傳當月用量物件", async () => {
    mock.onGet("/users/me/quota").reply(200, {
      data: {
        used_usd: "12.30",
        limit_usd: "50.00",
        allowed: true,
        percentage: 24.6,
      },
    });
    const { result } = renderHook(() => useMyQuota(), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.used_usd).toBe("12.30");
    expect(result.current.data?.allowed).toBe(true);
    expect(result.current.data?.percentage).toBeCloseTo(24.6);
  });
});
