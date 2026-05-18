"""Phase 11 — ExportsService：PDF / MD / XLSX 匯出。

依 PLAN.md ADR-010：PDF 用 Playwright + chromium。

設計：
- export_pdf: Jinja2 render HTML → Playwright render → bytes
- export_md: 直接從 analysis_reports.report_md，加上 metadata header
- export_xlsx: openpyxl 組裝（單張 sheet：摘要 + KPI + 辯論過程）

字型：Dockerfile 已裝 fonts-noto-cjk；HTML CSS 指定 'Noto Sans CJK TC' fallback。
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from jinja2 import Environment, select_autoescape

from app.core.errors import ConflictError, ExternalServiceError, NotFoundError
from app.core.logging_config import get_logger
from app.repos.analysis_repo import AnalysisRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.analysis import AnalysisReport
    from app.models.user import User

logger = get_logger(__name__)


# Jinja2 minimal HTML template — CJK font via @font-face fallback chain
_PDF_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<title>{{ symbol }} 分析報告</title>
<style>
  @page { size: A4; margin: 18mm; }
  body {
    font-family: 'Noto Sans CJK TC', 'Noto Sans TC', 'Microsoft JhengHei',
                 'PingFang TC', 'Source Han Sans TC', sans-serif;
    color: #222; line-height: 1.6; font-size: 12pt;
  }
  h1 { font-size: 20pt; border-bottom: 2px solid #1f77b4; padding-bottom: 4mm; }
  h2 { font-size: 14pt; margin-top: 6mm; color: #1f77b4; }
  .meta { color: #666; font-size: 10pt; margin-bottom: 6mm; }
  .signal-BUY, .signal-STRONG_BUY { color: #2e7d32; font-weight: bold; }
  .signal-SELL, .signal-STRONG_SELL { color: #c62828; font-weight: bold; }
  .signal-HOLD { color: #f9a825; font-weight: bold; }
  pre { background: #f5f5f5; padding: 4mm; white-space: pre-wrap; word-wrap: break-word; }
  table { border-collapse: collapse; width: 100%; margin: 4mm 0; }
  th, td { border: 1px solid #ddd; padding: 2mm 3mm; text-align: left; }
  th { background: #fafafa; }
</style>
</head>
<body>
  <h1>{{ symbol }} ({{ market }}) 分析報告</h1>
  <div class="meta">
    <div>分析 ID：{{ analysis_id }}</div>
    <div>建立時間：{{ created_at }}</div>
    <div>產生時間：{{ generated_at }}</div>
  </div>

  <h2>投資建議</h2>
  <p>訊號：<span class="signal-{{ signal or 'HOLD' }}">{{ signal_zh }}</span></p>
  <table>
    <tr><th>信心</th><td>{{ confidence_pct }}</td></tr>
    <tr><th>目標價</th><td>{{ target_price or '—' }}</td></tr>
    <tr><th>停損</th><td>{{ stop_loss or '—' }}</td></tr>
    <tr><th>停利</th><td>{{ take_profit or '—' }}</td></tr>
  </table>

  <h2>使用 LLM</h2>
  <table>
    <tr><th>Provider / Model</th><td>{{ llm_provider or '—' }} / {{ llm_model or '—' }}</td></tr>
    <tr><th>Tokens</th><td>{{ total_tokens }}</td></tr>
    <tr><th>成本 (USD)</th><td>{{ total_cost_usd }}</td></tr>
  </table>

  <h2>分析報告</h2>
  <pre>{{ report_md or '尚無報告內容' }}</pre>
</body>
</html>
"""


_SIGNAL_ZH = {
    "BUY": "買進",
    "STRONG_BUY": "強烈買進",
    "SELL": "賣出",
    "STRONG_SELL": "強烈賣出",
    "HOLD": "持有",
    None: "持有",
}


class ExportsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AnalysisRepository(session)

    async def _load_for_user(self, user: User, report_id: UUID) -> AnalysisReport:
        from app.core.errors import ForbiddenError

        report = await self.repo.get_by_id(report_id)
        if report is None:
            raise NotFoundError(message_zh="分析不存在", analysis_id=str(report_id))
        if user.role.upper() != "ADMIN" and report.user_id != user.id:
            raise ForbiddenError(message_zh="無權匯出他人的分析")
        if report.status != "completed":
            raise ConflictError(
                message_zh="分析尚未完成，無法匯出",
                status=report.status,
            )
        return report

    # ── MD ───────────────────────────────────────────
    async def export_md(self, user: User, report_id: UUID) -> str:
        report = await self._load_for_user(user, report_id)
        header = (
            f"# {report.symbol} ({report.market}) 分析報告\n\n"
            f"- 分析 ID：{report.id}\n"
            f"- 建立時間：{report.created_at.isoformat()}\n"
            f"- 投資建議：{_SIGNAL_ZH.get(report.signal, '—')}\n"
            f"- 信心：{report.confidence if report.confidence is not None else '—'}\n\n"
            "---\n\n"
        )
        return header + (report.report_md or "尚無報告內容")

    # ── XLSX ─────────────────────────────────────────
    async def export_xlsx(self, user: User, report_id: UUID) -> bytes:
        try:
            from openpyxl import Workbook
        except ImportError as e:  # pragma: no cover
            raise ExternalServiceError(message_zh="openpyxl 未安裝") from e

        report = await self._load_for_user(user, report_id)
        wb = Workbook()
        ws = wb.active
        ws.title = "Summary"
        rows = [
            ["欄位", "值"],
            ["Symbol", report.symbol],
            ["Market", report.market],
            ["Status", report.status],
            ["Signal", _SIGNAL_ZH.get(report.signal, "—")],
            ["Confidence", str(report.confidence) if report.confidence is not None else ""],
            ["Target Price", str(report.target_price) if report.target_price is not None else ""],
            ["Stop Loss", str(report.stop_loss) if report.stop_loss is not None else ""],
            ["Take Profit", str(report.take_profit) if report.take_profit is not None else ""],
            ["LLM Model", report.llm_model or ""],
            ["Total Tokens", report.total_tokens],
            ["Total Cost USD", str(report.total_cost_usd)],
            ["Created At", report.created_at.isoformat()],
        ]
        for row in rows:
            ws.append(row)

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    # ── PDF ──────────────────────────────────────────
    async def export_pdf(self, user: User, report_id: UUID) -> bytes:
        try:
            from playwright.async_api import async_playwright
        except ImportError as e:
            raise ExternalServiceError(
                message_zh="Playwright 未安裝，請執行 playwright install"
            ) from e

        report = await self._load_for_user(user, report_id)
        html = self._render_html(report)
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
                try:
                    page = await browser.new_page()
                    await page.set_content(html, wait_until="domcontentloaded")
                    pdf_bytes = await page.pdf(format="A4", print_background=True)
                finally:
                    await browser.close()
        except Exception as e:  # pragma: no cover - depends on environment
            logger.warning("exports.pdf.failed", error=str(e), error_type=type(e).__name__)
            raise ExternalServiceError(
                message_zh="PDF 產生失敗（chromium 不可用）",
                source="playwright",
            ) from e
        return pdf_bytes

    def _render_html(self, report: AnalysisReport) -> str:
        env = Environment(autoescape=select_autoescape(["html"]))
        tmpl = env.from_string(_PDF_TEMPLATE)
        confidence_pct = (
            f"{float(report.confidence) * 100:.1f}%" if report.confidence is not None else "—"
        )
        return tmpl.render(
            symbol=report.symbol,
            market=report.market,
            analysis_id=str(report.id),
            created_at=report.created_at.isoformat(),
            generated_at=datetime.now(UTC).isoformat(),
            signal=report.signal,
            signal_zh=_SIGNAL_ZH.get(report.signal, "—"),
            confidence_pct=confidence_pct,
            target_price=str(report.target_price) if report.target_price is not None else None,
            stop_loss=str(report.stop_loss) if report.stop_loss is not None else None,
            take_profit=str(report.take_profit) if report.take_profit is not None else None,
            llm_provider=report.llm_provider,
            llm_model=report.llm_model,
            total_tokens=report.total_tokens,
            total_cost_usd=str(report.total_cost_usd),
            report_md=report.report_md,
        )


__all__ = ["ExportsService"]
