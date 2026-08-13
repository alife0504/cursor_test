"use client";

import "highlight.js/styles/github.css";

import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

interface ReportMarkdownProps {
  source?: string | null;
  className?: string;
}

// Phase 16 § E:report_md 渲染
//   - remark-gfm:表格 / strikethrough / task list
//   - rehype-highlight:程式碼語法高亮
//   - 不依賴 @tailwindcss/typography(專案未安裝),手動樣式各 element
export function ReportMarkdown({ source, className }: ReportMarkdownProps) {
  if (!source) {
    return (
      <p className="text-sm text-muted-foreground">
        報告尚未產生。分析完成後會自動填入此處。
      </p>
    );
  }
  return (
    <div className={cn("space-y-2 text-sm leading-relaxed", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          h1: ({ children }) => (
            <h1 className="mb-2 mt-4 text-2xl font-bold">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-2 mt-3 text-xl font-semibold">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-1 mt-2 text-lg font-semibold">{children}</h3>
          ),
          p: ({ children }) => <p className="my-2">{children}</p>,
          ul: ({ children }) => (
            <ul className="my-2 list-inside list-disc space-y-1">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="my-2 list-inside list-decimal space-y-1">
              {children}
            </ol>
          ),
          li: ({ children }) => <li className="ml-2">{children}</li>,
          table: ({ children }) => (
            <div className="my-2 overflow-x-auto rounded-md border">
              <table className="min-w-full text-xs">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border-b bg-muted/40 px-2 py-1 text-left font-semibold">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border-b px-2 py-1">{children}</td>
          ),
          code: ({ children, className: cls }) => {
            const isInline = !cls;
            if (isInline) {
              return (
                <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">
                  {children}
                </code>
              );
            }
            return <code className={cls}>{children}</code>;
          },
          pre: ({ children }) => (
            <pre className="my-2 overflow-x-auto rounded-md bg-muted/40 p-3 text-xs">
              {children}
            </pre>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-2 border-l-2 border-muted-foreground/40 pl-3 italic text-muted-foreground">
              {children}
            </blockquote>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline"
            >
              {children}
            </a>
          ),
        }}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
}
