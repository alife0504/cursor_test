# Obsidian 個人筆記整合 — 安裝與設定

> v1.0 — **可選**功能（不影響核心分析平台）。
> v1.1 才會做「自動匯出分析報告到 vault」；目前是手動。

---

## 1. 為什麼用 Obsidian

`分析報告`（markdown） + `個人投資筆記`（你自己寫的）放同一個 vault，用 Dataview 跨檔查詢：

- 「過去 7 天 BUY 訊號的股票」
- 「同一股票 3 次以上分析的訊號變化」
- 「我看好但 AI 看空的股票」

純文字 / 純本地、完全離線、不會 vendor lock-in。

---

## 2. 安裝

### Windows

1. https://obsidian.md/download → 下載 Windows Installer
2. 雙擊安裝（無需管理員權限，預設裝 `%LOCALAPPDATA%\Obsidian\`）
3. 啟動 Obsidian

### macOS

1. https://obsidian.md/download → 下載 `.dmg`
2. 拖到 Applications

### Linux

```bash
# AppImage（最簡單）
wget https://github.com/obsidianmd/obsidian-releases/releases/latest/download/Obsidian-*.AppImage -O ~/Obsidian.AppImage
chmod +x ~/Obsidian.AppImage
~/Obsidian.AppImage
```

或用 Flatpak：
```bash
flatpak install flathub md.obsidian.Obsidian
```

### 驗證安裝

```bash
bash scripts/check_obsidian_installed.sh
```

---

## 3. 建立 vault

1. 打開 Obsidian → 第一次會問「Create new vault」/「Open folder as vault」
2. 選擇 **「Open folder as vault」**
3. 路徑填：`C:/Projects/TradingAgents/obsidian_vault`（Linux/macOS：`~/TradingAgents/obsidian_vault`）
4. 進入 vault 後：Settings → About → Use Optimized Editor: ON

> 注意：vault 路徑不要放在 git repo 內 git 追蹤的位置。若一定要放在 repo 內，加到 `.gitignore`（v1.0 預設 `obsidian_vault/` 已在 `.gitignore`）。

---

## 4. 必裝 Community Plugin（3 個）

啟用 Community Plugins：Settings → Community plugins → Turn on（首次會警告：你正在使用第三方）。

### 4.1 Templater

用於：套用 daily note / 報告 import 模板。

1. Browse → 搜尋「Templater」→ Install → Enable
2. Settings → Templater → Template folder：`templates`

### 4.2 Dataview

用於：跨檔查詢分析報告（核心功能）。

1. Browse → 「Dataview」→ Install → Enable
2. Settings → Dataview → Enable JavaScript Queries: ON

### 4.3 Calendar

用於：左側日曆 quick switch 到 daily notes。

1. Browse → 「Calendar」→ Install → Enable

---

## 5. 建議的 vault 結構

```
obsidian_vault/
├── reports/                          ← TradingAgents 匯出的 markdown
│   ├── 2026-05-18/
│   │   ├── 2330-analysis.md          ← AI 報告
│   │   └── AAPL-analysis.md
│   └── 2026-05-19/
│       └── ...
├── notes/                            ← 你的個人投資筆記
│   ├── daily/
│   │   └── 2026-05-18.md             ← daily note
│   ├── weekly/
│   │   └── 2026-W20.md               ← weekly review
│   └── stocks/
│       ├── 2330.md                   ← 「我對台積電的長期觀察」
│       └── AAPL.md
├── templates/
│   ├── daily.md
│   ├── weekly.md
│   ├── stock-note.md
│   └── analysis-import.md
└── .obsidian/                        ← 工具自動產生
```

建議用 `mkdir`：

```bash
mkdir -p obsidian_vault/{reports,notes/{daily,weekly,stocks},templates}
```

---

## 6. 推薦模板（手動建立）

### 6.1 daily.md

```markdown
---
date: <% tp.date.now("YYYY-MM-DD") %>
type: daily
---

# <% tp.date.now("YYYY-MM-DD") %> Daily

## 今日大盤
- TWSE 收盤：
- 加權成交量：

## 今日操作
-

## 觀察清單
-

## AI 分析摘要
```dataview
TABLE
  symbol AS 股票,
  signal.action AS 訊號,
  signal.confidence AS 信心,
  file.link AS 報告
FROM "reports"
WHERE date = date(this.file.name)
```

## 反思
-
```

### 6.2 stock-note.md

```markdown
---
symbol:
market:
created: <% tp.date.now("YYYY-MM-DD") %>
tags: [stock]
---

# {{symbol}} —

## 為什麼關注

## 我的看法

## 風險

## 觀察點

## AI 分析歷史
```dataview
TABLE
  signal.action AS 訊號,
  signal.confidence AS 信心,
  date,
  file.link AS 報告
FROM "reports"
WHERE symbol = "{{symbol}}"
SORT date DESC
```
```

---

## 7. 手動匯入分析報告（v1.0 流程）

1. 在 TradingAgents Web `/analysis/[id]` 右上「⋮」→ 匯出 Markdown
2. 把下載的 .md 移到 `obsidian_vault/reports/<日期>/`
3. **重要**：檔案開頭必須有 frontmatter（系統匯出已附），格式：

```yaml
---
symbol: 2330
market: TWSE
date: 2026-05-18
signal:
  action: BUY
  confidence: 0.78
  target_price: 920
  stop_loss: 850
created_at: 2026-05-18T10:23:45Z
tags: [analysis, ai]
---
```

Dataview 用這個 frontmatter 查詢。

v1.1 會做自動匯出（系統直接寫 `<vault>/reports/<日期>/`）。

---

## 8. Dataview 範例查詢

放在 daily note 或單獨 `.md`：

### 過去 7 天的 BUY 訊號

```dataview
TABLE
  symbol AS 股票,
  signal.confidence AS 信心,
  signal.target_price AS 目標價,
  date AS 分析日期
FROM "reports"
WHERE signal.action = "BUY"
  AND date >= date(today) - dur(7 days)
SORT signal.confidence DESC
```

### 同一股票多次分析的訊號變化

```dataview
TABLE WITHOUT ID
  file.link AS 報告,
  date,
  signal.action AS 訊號,
  signal.confidence AS 信心
FROM "reports"
WHERE symbol = "2330"
SORT date DESC
```

### 高信心 BUY 但我尚未做筆記

```dataview
LIST
  "AI 強烈推薦但我沒筆記：" + file.link
FROM "reports"
WHERE signal.action = "BUY"
  AND signal.confidence > 0.75
  AND !any(file.outlinks, (l) => contains(l.file.folder, "notes/stocks"))
```

---

## 9. 同步到雲端（可選）

Obsidian 預設離線。如要跨裝置同步：

| 方式 | 月費 | 推薦度 |
|------|------|-------|
| Obsidian Sync（官方） | $4/月 | ⭐⭐⭐⭐⭐ 最簡單、加密 |
| Syncthing（自架） | 免費 | ⭐⭐⭐⭐ 需要自己跑 |
| Git（手動 commit） | 免費 | ⭐⭐⭐ 適合會 git 的人 |
| iCloud / OneDrive / Dropbox | 已付過 | ⭐⭐ 偶爾 race condition |

v1.0 自用建議直接本地，不同步。

---

## 10. 與 TradingAgents v1.0 的關係

- **不會 import 任何 Obsidian 資料到平台**：vault 是「外部副本 + 個人加值」
- **分析報告是 source of truth**：DB + 匯出 .md 是主，vault 是延伸
- **未來 v1.1 自動匯出**：v1.0 手動 → v1.1 系統 cron 寫入 → v2.0 雙向同步

---

## 11. 常見問題

### Q1：vault 一定要叫這個名字 / 路徑嗎？
不一定。但 `check_obsidian_installed.sh` 預設提示路徑。如果你選別的，自己記得即可。

### Q2：可以把 vault 放進 git 嗎？
- 個人筆記：可以，但加上私人 remote
- 報告：建議不加入（資料量會膨脹）
- 預設 `.gitignore` 已排除 `obsidian_vault/`

### Q3：Dataview 查不到 frontmatter？
- 確認 frontmatter 在檔案最頂端（前後 `---` 包圍）
- YAML 縮排嚴格用空格（不能用 Tab）
- Restart Obsidian 強制重新索引

### Q4：v1.1 的自動匯出會覆蓋我手動加的內容嗎？
規劃中：自動匯出寫到 `reports/`（系統管理）；個人補充寫到 `notes/`（你管理）。兩邊用 `[[2330|台積電]]` 連結。

---

## 12. 進階：把 vault 加進 TradingAgents

v1.1 計畫做：
1. backend 環境變數 `OBSIDIAN_VAULT_PATH=/path/to/vault`
2. analysis.completed 事件 → 寫到 `<vault>/reports/<日期>/`
3. `/admin/system` 顯示 vault 統計（總檔案數、最新匯出時間）

v1.0 不做。

---

完成 vault 建立、3 個 plugin 安裝、第一個 daily note → Obsidian 整合完成。
