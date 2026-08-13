# 還原（後悔藥）— 大修前的安全網

大修怕修壞？這份是你的「反悔鍵」。三層都有還原點，失敗一定回得去。

## 穩定還原點：`stable-2026-08-13`
建立於多輪深度審查修補＋全面驗證通過後的已知良好狀態。

| 層 | 還原點 | 位置 |
|---|---|---|
| 程式碼 | git tag `stable-2026-08-13` | 已 push 到 origin（連硬碟壞了都在） |
| 系統 image | `tradingagents-backend:stable-2026-08-13`、`tradingagents-frontend:stable-2026-08-13` | 本機 docker |
| 資料庫 | `backups/tradingagents_tw-stable-2026-08-13.dump`（pg_dump -Fc，103MB） | 本機（未進版控） |

## 怎麼還原

### 一鍵還原程式碼 + 系統（最常用，涵蓋 9 成「修壞了」情況）
```powershell
./scripts/restore-to-stable.ps1
```
- 自動把你未提交的大修 WIP `git stash` 起來（不會遺失，`git stash pop` 救得回）
- 程式碼切回 `stable-2026-08-13`、image 還原成穩定快照、重新部署
- **你的大修分支原封不動**——還想繼續大修就 `git checkout 你的分支`

### 連資料庫也還原（僅在資料被改壞，例如壞的 migration）
```powershell
./scripts/restore-to-stable.ps1 -RestoreData
```
- 會問你 `YES` 確認才覆蓋 DB；用 TimescaleDB 正確程序（pre/post_restore）還原

## 大修的安全姿勢
1. 開新分支：`git checkout -b big-refactor`（穩定 tag 完全不動）
2. 小步 commit（每次一個邏輯單元，pre-commit 會跑 ruff/測試把關）
3. 測試綠燈才部署；覺得不對 → `./scripts/restore-to-stable.ps1`
4. 大修成功再合併；失敗就丟掉分支，當沒發生過

## 之後要更新穩定點（大修成功並穩定後）
```bash
git tag -a stable-YYYY-MM-DD -m "新的穩定還原點" && git push origin stable-YYYY-MM-DD
docker tag tradingagents-backend:dev tradingagents-backend:stable-YYYY-MM-DD
docker tag tradingagents-frontend:dev tradingagents-frontend:stable-YYYY-MM-DD
docker exec ta-timescaledb sh -c 'PGPASSWORD=$POSTGRES_PASSWORD pg_dump -U postgres -Fc --no-owner tradingagents_tw' > backups/tradingagents_tw-stable-YYYY-MM-DD.dump
```
