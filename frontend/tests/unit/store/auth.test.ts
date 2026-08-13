import { beforeEach, describe, expect, test } from "vitest";

import { useAuthStore } from "@/store/auth";

describe("useAuthStore", () => {
  beforeEach(() => {
    useAuthStore.getState().logout();
  });

  test("初始為 null", () => {
    const s = useAuthStore.getState();
    expect(s.accessToken).toBeNull();
    expect(s.user).toBeNull();
  });

  test("setAccessToken 更新 token", () => {
    useAuthStore.getState().setAccessToken("abc");
    expect(useAuthStore.getState().accessToken).toBe("abc");
  });

  test("setUser 更新 user", () => {
    useAuthStore.getState().setUser({
      id: "1",
      email: "a@b.com",
      role: "ADMIN",
    });
    expect(useAuthStore.getState().user?.email).toBe("a@b.com");
  });

  test("logout 清空", () => {
    useAuthStore.getState().setAccessToken("x");
    useAuthStore.getState().setUser({ id: "1", email: "a", role: "ADMIN" });
    useAuthStore.getState().logout();
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
  });
});
