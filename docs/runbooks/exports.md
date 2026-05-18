# Runbook：分析報告匯出（PDF / MD / XLSX）

依 ADR-010：PDF 走 Playwright + chromium。本文件記載常見故障排查。

---

## 0. Endpoint 速覽

| Method | Path | 說明 |
|--------|------|------|
| GET | `/api/v1/exports/{report_id}?format=pdf` | application/pdf |
| GET | `/api/v1/exports/{report_id}?format=md` | text/markdown; charset=utf-8 |
| GET | `/api/v1/exports/{report_id}?format=xlsx` | xlsx（openpyxl） |

**權限**：報告擁有者本人 / ADMIN；分析必須 `status == completed`。

---

## 1. 中文亂碼

### 症狀

PDF 內中文顯示為「□」、「○」或空白方塊。

### 原因

容器內缺 CJK 字型（fontconfig 找不到對應字面）。

### 排查

```bash
# 進容器看字型
docker compose exec backend fc-list :lang=zh-tw | head

# 若沒輸出 → 缺字型
```

### 修法

`backend/Dockerfile` 必含：

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*
```

`exports_service._PDF_TEMPLATE` 的 CSS 預設 fallback 鏈：

```css
font-family: 'Noto Sans CJK TC', 'Noto Sans TC', 'Microsoft JhengHei',
             'PingFang TC', 'Source Han Sans TC', sans-serif;
```

重 build：

```bash
docker compose build backend && docker compose up -d backend
```

---

## 2. Playwright 啟動失敗

### 症狀

```
ExternalServiceError: PDF 產生失敗（chromium 不可用）
```

```
playwright._impl._errors.Error: BrowserType.launch: Executable doesn't exist at ...
```

### 排查

```bash
# 確認 binary 在容器內
docker compose exec backend ls -la /ms-playwright

# 應該看到 chromium-* 目錄
```

### 修法

```dockerfile
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN mkdir -p $PLAYWRIGHT_BROWSERS_PATH \
    && uv run playwright install-deps chromium \
    && uv run playwright install chromium \
    && chmod -R o+rx $PLAYWRIGHT_BROWSERS_PATH

# runtime user 也要設這個 env
ENV ... PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
```

---

## 3. chromium 需要 --no-sandbox

### 症狀

```
Failed to launch chromium because executable doesn't exist
```

或：

```
error: Failed to move to new namespace: PID namespaces supported, ...
```

### 原因

Docker container 內 chromium 預設帶 sandbox（chroot+namespaces），多數 base image 沒給足夠 capability。

### 修法

`exports_service.export_pdf` 已寫死：

```python
browser = await p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
```

不要拿掉。

---

## 4. /api/v1/exports 回 409 「分析尚未完成」

### 原因

`analysis.status != "completed"`（可能還在 queued/running，或 failed/cancelled）。

### 修法

不是 bug；先等 P12+ LangGraph workflow 跑完。手動測試可直接改 DB：

```sql
UPDATE analysis_reports
   SET status='completed', report_md='# 測試報告'
 WHERE id='<analysis_id>';
```

---

## 5. /api/v1/exports 回 403 「無權匯出他人的分析」

### 原因

IDOR 防護：非 admin 只能匯出自己的分析。

### 修法

用該 analysis 的擁有者帳號登入；或用 admin。

---

## 6. xlsx 缺欄位 / 亂碼

`openpyxl` 預設 utf-8 編碼，不該亂碼。若有：

```bash
# 直接看 raw bytes，確認 PK header 與 sharedStrings 內容
curl -fsS -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/exports/$ID?format=xlsx" \
  -o /tmp/r.xlsx
file /tmp/r.xlsx          # 應為 "Microsoft Excel 2007+"
unzip -p /tmp/r.xlsx xl/sharedStrings.xml | head -50
```

若 sharedStrings 內就亂碼 → 是 ORM 取出的 `report_md` 已壞，回頭看 DB encoding（`SHOW server_encoding;` 應為 UTF8）。

---

## 7. 健康檢查

phase_11.sh 第 9 項會自動驗 PDF magic header；本地無 chromium 時自動降級為 MD 匯出測試（不會擋住健檢）。
