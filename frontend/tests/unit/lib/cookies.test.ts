/**
 * @vitest-environment jsdom
 */
import { describe, expect, test } from "vitest";

import { getCookie } from "@/lib/cookies";

describe("getCookie", () => {
  test("讀取存在的 cookie", () => {
    document.cookie = "foo=bar; path=/";
    expect(getCookie("foo")).toBe("bar");
  });

  test("不存在回 null", () => {
    expect(getCookie("not-exist-xxx-yyy")).toBeNull();
  });

  test("URI encoded 值會自動 decode", () => {
    document.cookie = "csrf_token=abc%20xyz; path=/";
    expect(getCookie("csrf_token")).toBe("abc xyz");
  });
});
