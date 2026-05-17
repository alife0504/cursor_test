/**
 * @vitest-environment jsdom
 */
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

// 用 axios-mock-adapter 攔 api 實例(不打網路)
let mock: MockAdapter;

beforeEach(async () => {
  // 動態載入避免影響其他不 mock 的 test
  const { default: MA } = await import("axios-mock-adapter");
  mock = new MA(api);
  useAuthStore.getState().logout();
});

afterEach(() => {
  mock.restore();
  vi.restoreAllMocks();
});

describe("api interceptor", () => {
  test("成功 GET 不變動", async () => {
    mock.onGet("/ping").reply(200, { data: "pong" });
    const r = await api.get("/ping");
    expect(r.status).toBe(200);
  });

  test("/auth/login 401 不會走 refresh,直接 reject", async () => {
    let refreshHit = false;
    mock.onPost("/auth/login").reply(401, { error: "INVALID_CREDENTIALS" });
    mock.onPost("/auth/refresh").reply(() => {
      refreshHit = true;
      return [401];
    });

    await expect(
      api.post("/auth/login", { email: "x", password: "y" }),
    ).rejects.toMatchObject({ response: { status: 401 } });

    expect(refreshHit).toBe(false);
  });

  test("一般 endpoint 401 會嘗試 refresh 一次,refresh 成功則 retry", async () => {
    const newToken = "new-access-token";
    mock
      .onGet("/users/me")
      .replyOnce(401)
      .onGet("/users/me")
      .reply(200, { data: { id: "1" } });
    mock
      .onPost("/auth/refresh")
      .reply(200, { data: { access_token: newToken } });

    const r = await api.get("/users/me");
    expect(r.status).toBe(200);
    expect(useAuthStore.getState().accessToken).toBe(newToken);
  });

  test("refresh 自己 401 不會無限迴圈,只試一次", async () => {
    let refreshCount = 0;
    mock.onGet("/users/me").reply(401);
    mock.onPost("/auth/refresh").reply(() => {
      refreshCount++;
      return [401];
    });
    // jsdom 沒有 location.href 寫權限保護,vi mock 一個 noop
    const original = window.location.href;
    Object.defineProperty(window, "location", {
      writable: true,
      value: { ...window.location, href: original, pathname: "/", search: "" },
    });

    await expect(api.get("/users/me")).rejects.toBeDefined();
    expect(refreshCount).toBe(1);
  });
});

describe("CSRF header", () => {
  test("POST 自動帶 X-CSRF-Token", async () => {
    document.cookie = "csrf_token=tkt-xyz; path=/";
    let receivedHeader: string | undefined;
    mock.onPost("/stocks").reply((config) => {
      receivedHeader = config.headers?.["X-CSRF-Token"] as string;
      return [200, { data: [] }];
    });
    await api.post("/stocks", {});
    expect(receivedHeader).toBe("tkt-xyz");
  });

  test("GET 不帶 X-CSRF-Token", async () => {
    document.cookie = "csrf_token=tkt-zzz; path=/";
    let receivedHeader: string | undefined;
    mock.onGet("/stocks").reply((config) => {
      receivedHeader = config.headers?.["X-CSRF-Token"] as string;
      return [200, { data: [] }];
    });
    await api.get("/stocks");
    expect(receivedHeader).toBeUndefined();
  });
});

describe("Bearer header", () => {
  test("有 token 自動帶 Authorization", async () => {
    useAuthStore.getState().setAccessToken("abc");
    let receivedAuth: string | undefined;
    mock.onGet("/me").reply((config) => {
      receivedAuth = config.headers?.Authorization as string;
      return [200, { data: {} }];
    });
    await api.get("/me");
    expect(receivedAuth).toBe("Bearer abc");
  });

  test("沒 token 不帶 Authorization", async () => {
    let receivedAuth: string | undefined;
    mock.onGet("/me").reply((config) => {
      receivedAuth = config.headers?.Authorization as string;
      return [200, { data: {} }];
    });
    await api.get("/me");
    expect(receivedAuth).toBeUndefined();
  });
});
