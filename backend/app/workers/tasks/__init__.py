"""Celery task 模組集合。

每個子模組註冊一組 task：
- sync_ohlcv：OHLCV 同步（TW + US，fan-out 批次）
- news_ingest：新聞抓取
- financial：財務報表 / 月營收 / 三大法人
- cleanup：orphan / idempotency_keys / notification_log
- verify_audit：audit chain 校驗（P7 為 stub，P9 升級）

import 此 package 即 import 所有子模組（透過 celery_app.include 設定）。
"""
