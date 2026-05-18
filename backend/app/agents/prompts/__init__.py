"""prompt 模板集中目錄（純 .txt 檔，與程式邏輯分離）。

讀取方式：
    from app.agents.prompts_loader import load_prompt
    txt = load_prompt("market_analyst_system")

設計：
- 每個 prompt 含：角色定位、tool 清單、輸出格式要求、限制、繁中表述。
- 命名規範：{role}_{kind}.txt  其中 kind ∈ {system, user_tw_template, user_us_template}。
- P13 先建 TW 版（market/fundamental/news/sentiment），US 版在 P14 補。

此 package 主要是讓 importlib.resources 能正確定位資源檔。
"""
