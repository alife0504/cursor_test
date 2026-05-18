import { describe, expect, test } from "vitest";

import { getLocale, setLocale, t } from "@/i18n/messages";

describe("i18n", () => {
  test("預設 locale 是 zh-TW", () => {
    expect(getLocale()).toBe("zh-TW");
  });

  test("已存在的 key 回中文", () => {
    expect(t("nav.dashboard")).toBe("儀表板");
  });

  test("不存在的 key 回 key 本身", () => {
    expect(t("not.exist.key.deadbeef")).toBe("not.exist.key.deadbeef");
  });

  test("切到 en 仍有 fallback 到 zh-TW", () => {
    setLocale("en");
    expect(getLocale()).toBe("en");
    // app.title 在 en 也有定義
    expect(t("app.title")).toBe("TradingAgents-TW");
    // nav.dashboard 在 en 沒定義 → fallback zh-TW
    expect(t("nav.dashboard")).toBe("儀表板");
    setLocale("zh-TW");
  });
});
