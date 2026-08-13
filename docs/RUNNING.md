# 穩定運行指南（避免網站隨時停止服務）

「網站隨時停止服務」的根因不是程式 bug，而是**執行方式**：
backend(`uvicorn`)、frontend(`next dev`) 若以**前景 dev server** 跑在本機，
沒有任何監督 —— 崩潰、關掉終端機、筆電休眠、`--reload` 在壞檔存檔時都會讓它停掉**且不會自己回來**。

Docker compose 內所有服務都已設 `restart: unless-stopped`（prod 為 `restart: always`），
所以**把整個 web tier 容器化跑**就會自動重啟、開機自啟、不再隨意停止。

---

## ✅ 推薦：全棧持續運行（一個指令）

```bash
make stack-up      # infra + backend + worker + beat + frontend，全部自動重啟
make stack-ps      # 看狀態
make stack-logs    # 跟 log
make stack-down    # 停止（保留資料）
make stack-restart # 改了程式碼後重建並重啟
```

- 第一次會 `--build`（前端 prod build 需數分鐘），之後啟動很快。
- 容器崩潰 → Docker 自動重啟；Docker Desktop 開機自啟 → 整站自動拉起。
- 已處理 Windows 保留 port：redis/qdrant 發佈到 16379/16333，**內網仍走 6379/6333**，
  backend 在容器網路內直接連 `redis:6379` / `qdrant:6333`，不受保留 port 影響。
- 入口：前端 <http://localhost:3000>、後端 <http://localhost:8000/health/ready>。

## 開發替代：本機自動重啟（保留前端 HMR）

想邊改前端邊看 HMR、又要 backend 崩潰自動回來：

```powershell
./scripts/run-host-supervised.ps1
```

會開兩個監督視窗（backend / frontend），任一退出 3 秒後自動重啟。
（關掉視窗即停止；要真正常駐請用 `make stack-up`。）

> 不要再用 `make backend-dev`（`uvicorn --reload`）當常駐：`--reload` 在語法錯誤存檔時會直接掛掉不回來。

---

## 程式層韌性（本輪已加）

- **啟動探測退避重試**：DB/Redis/Qdrant 在啟動時短暫不可用（冷啟排序 / 休眠喚醒 / redis 重啟）
  會重試（`STARTUP_PROBE_RETRIES`，預設 10 次退避）而非一啟動就 raise 殺掉 process；用盡才 fail-fast。
- **連線自癒**：DB engine `pool_pre_ping` + `pool_recycle=300`；Redis pool `health_check_interval` +
  `retry_on_timeout` —— 休眠喚醒 / 服務重啟後，失效連線會自動重建，不會卡死整站。

## 還是會停？把當機現場抓下來

若仍偶發停止，請保留崩潰當下的 log 再回報：

```bash
make stack-logs                          # 容器化：看 backend/frontend 退出原因
docker compose --profile frontend ps     # 看哪個容器 Restarting / Exited
# 本機跑法：監督視窗會印出退出訊息（exit code / traceback）
```
