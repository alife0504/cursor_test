import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

const pathRef = { value: "/dashboard" };

vi.mock("next/navigation", () => ({
  usePathname: () => pathRef.value,
}));

import { Breadcrumbs } from "@/components/common/Breadcrumbs";

describe("<Breadcrumbs />", () => {
  test("/dashboard 不顯示麵包屑（一段不顯）", () => {
    pathRef.value = "/dashboard";
    const { container } = render(<Breadcrumbs />);
    expect(container.firstChild).toBeNull();
  });

  test("/admin/users 顯示「管理 > 用戶管理」並含 home 連結", () => {
    pathRef.value = "/admin/users";
    render(<Breadcrumbs />);
    expect(screen.getByText("管理")).toBeInTheDocument();
    expect(screen.getByText("用戶管理")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "首頁" })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });

  test("動態 UUID 段顯示為「詳情」", () => {
    pathRef.value = "/analysis/123e4567-e89b-12d3-a456-426614174000";
    render(<Breadcrumbs />);
    expect(screen.getByText("AI 分析")).toBeInTheDocument();
    expect(screen.getByText("詳情")).toBeInTheDocument();
  });
});
