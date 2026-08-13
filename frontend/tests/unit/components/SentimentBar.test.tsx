import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { SentimentBar } from "@/components/news/SentimentBar";
import type { NewsItem } from "@/lib/api-types";

// 由於 SentimentBar 內含動態 import 的 BarChart,
// 在 jsdom 中只 assert 標題 + 標題下方的 dom 結構就足夠

vi.mock("@/components/common/BarChart", () => ({
  BarChart: ({ data }: { data: Array<Record<string, unknown>> }) => (
    <div data-testid="bar-stub">
      {data.map((d, i) => (
        <span key={i} data-key={String(d.sentiment)}>{String(d.count)}</span>
      ))}
    </div>
  ),
}));

function mkNews(label: NonNullable<NewsItem["sentiment_label"]>): NewsItem {
  return {
    title: "t",
    published_at: "2025-01-01T00:00:00Z",
    sentiment_label: label,
  };
}

describe("<SentimentBar />", () => {
  // DB 的 sentiment 只有 positive / neutral / negative / unknown 四值
  // （後端 models/news.py SENTIMENT_VALUES + CHECK constraint）。
  // 舊版前端用 5 級（very_positive / very_negative）是死代碼，且完全不計 unknown →
  // 實際 99.7% 的新聞是 unknown 時整張圖恆為空。此處鎖定「4 桶且含未評級」。
  test("空輸入 → 4 bar 全 0（正面/中性/負面/未評級）", () => {
    render(<SentimentBar items={[]} />);
    expect(screen.getByText("情緒分佈")).toBeInTheDocument();
    const stub = screen.getByTestId("bar-stub");
    expect(stub.children.length).toBe(4);
    const keys = Array.from(stub.children).map(
      (c) => (c as HTMLElement).dataset.key,
    );
    expect(keys).toEqual(["正面", "中性", "負面", "未評級"]);
  });

  test("分類計數正確", () => {
    render(
      <SentimentBar
        items={[
          mkNews("very_positive"),
          mkNews("positive"),
          mkNews("positive"),
          mkNews("neutral"),
        ]}
      />,
    );
    const stub = screen.getByTestId("bar-stub");
    const cells = Array.from(stub.children) as HTMLElement[];
    const positiveCell = cells.find((c) => c.dataset.key === "正面");
    expect(positiveCell?.textContent).toBe("2");
    const neutralCell = cells.find((c) => c.dataset.key === "中性");
    expect(neutralCell?.textContent).toBe("1");
  });

  test("認不得的 label 不計入任何桶（不可偷偷算成中性）", () => {
    const it: NewsItem = {
      title: "x",
      published_at: "2025-01-01T00:00:00Z",
      sentiment_label: "some_unknown",
    };
    render(<SentimentBar items={[it]} />);
    const stub = screen.getByTestId("bar-stub");
    const cells = Array.from(stub.children) as HTMLElement[];
    // 不是 DB 允許值 → 不歸入中性（否則會謊報成「市場中性」）
    expect(cells.find((c) => c.dataset.key === "中性")?.textContent).toBe("0");
  });

  // 回歸守門：unknown 是 DB 的合法值且佔比可能極高，必須進「未評級」桶。
  // 舊版把 unknown 整個丟棄 → 分佈圖恆空，同時表格卻把它標成「中性」，兩邊自相矛盾。
  test("sentiment=unknown 計入「未評級」而非被丟棄", () => {
    render(
      <SentimentBar items={[mkNews("unknown"), mkNews("unknown")]} />,
    );
    const stub = screen.getByTestId("bar-stub");
    const cells = Array.from(stub.children) as HTMLElement[];
    expect(cells.find((c) => c.dataset.key === "未評級")?.textContent).toBe("2");
    expect(cells.find((c) => c.dataset.key === "中性")?.textContent).toBe("0");
  });
});
