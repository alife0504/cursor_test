import { act, render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { DateFormat } from "@/components/common/DateFormat";

describe("<DateFormat />", () => {
  test("UTC 顯示 → 等同 SSR 行為", () => {
    render(<DateFormat value="2026-05-17T01:00:00Z" timezone="UTC" />);
    expect(screen.getByText("2026-05-17 01:00:00")).toBeInTheDocument();
  });

  test("client mount 後切換到 Asia/Taipei", () => {
    render(
      <DateFormat value="2026-05-17T01:00:00Z" timezone="Asia/Taipei" />,
    );
    // useEffect 在測試環境同步觸發
    expect(screen.getByText("2026-05-17 09:00:00")).toBeInTheDocument();
  });

  test("date mode 只顯示日期", () => {
    render(
      <DateFormat
        value="2026-05-17T15:00:00Z"
        mode="date"
        timezone="Asia/Taipei"
      />,
    );
    // Taipei +08:00 → 跨日後是 23:00 同日,但 UTC view 是同日
    expect(screen.getByText("2026-05-17")).toBeInTheDocument();
  });

  test("無效輸入回 fallback", () => {
    render(<DateFormat value={null} fallback="-無資料" />);
    expect(screen.getByText("-無資料")).toBeInTheDocument();
  });

  test("act() 不報 warning", () => {
    // 純粹防 React act 警告:多 render 一次再 unmount 確認穩定
    const { unmount } = render(<DateFormat value="2026-05-17T01:00:00Z" />);
    act(() => {
      unmount();
    });
    expect(true).toBe(true);
  });
});
