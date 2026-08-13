import { describe, expect, test } from "vitest";

import { uuidv4 } from "@/lib/uuid";

describe("uuidv4", () => {
  test("回傳合法 UUID v4 字串", () => {
    const v = uuidv4();
    expect(v).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    );
  });

  test("連續 100 次不重複", () => {
    const set = new Set<string>();
    for (let i = 0; i < 100; i += 1) set.add(uuidv4());
    expect(set.size).toBe(100);
  });

  test("長度為 36", () => {
    expect(uuidv4().length).toBe(36);
  });
});
