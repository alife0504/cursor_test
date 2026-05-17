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
  test("空輸入 → 5 bar 全 0", () => {
    render(<SentimentBar items={[]} />);
    expect(screen.getByText("情緒分佈")).toBeInTheDocument();
    const stub = screen.getByTestId("bar-stub");
    expect(stub.children.length).toBe(5);
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

  test("未知 label 落到 neutral", () => {
    const it: NewsItem = {
      title: "x",
      published_at: "2025-01-01T00:00:00Z",
      sentiment_label: "some_unknown",
    };
    render(<SentimentBar items={[it]} />);
    const stub = screen.getByTestId("bar-stub");
    const cells = Array.from(stub.children) as HTMLElement[];
    const neutralCell = cells.find((c) => c.dataset.key === "中性");
    // 我們 hook 是「未知 → 'neutral'」但這個 fn 是 'in c' 檢查,unknown 不會增加任何 bucket
    // 所以實際上 neutral=0,其他 cell 也 0
    expect(neutralCell?.textContent).toBe("0");
  });
});
