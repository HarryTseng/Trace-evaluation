# Distributed Trace Sampling Strategies Evaluation

## 介紹
此專案為研究不同分散式追蹤取樣策略在不同拓樸、流量環境下的表現和開銷

## 使用
### 實驗腳本
1. generate.py

設定實驗環境，自動設定docker compose file
* NUM_SERVICES：服務數量
* TOPOLOGY_TYPE：拓樸方式
* COLLECTOR_IP：OpenTelemetry collector所在的ip
* HEAD_SAMPLING_RATE：head-based sampling率，0則是tail-based sampling

2. trace_check.py

檢查實驗輸出的traces.json裡多少trace有error

### 啟用
generate.py設定且執行過後，透過

`docker compose [--profile <collector/service>] up --build`
* --profile：若希望collector和microservice啟用在不同設備上，可指定啟用collector/service

## 研究歷程與里程碑
| 日期 | 事件 | 說明 |
| :---: | :---: | --- |
| **2026.06** | 115學年度大專學生研究計畫 | 名稱<br>探討微服務系統特性對Trace Sampling策略效能與成本之影響<br>編號<br>115-2813-C-004 -071 -E|
| **2026.07** | 第22屆台灣軟體工程研討會 | • 發表於TCSE 2026 <br> • 榮獲最佳英文論文獎|