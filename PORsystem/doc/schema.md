# 資料庫結構設計 (Database Schema)

## 1. User (用戶表)
- `id`: INTEGER (Primary Key)
- `username`: TEXT (Unique)
- `password_hash`: TEXT
- `is_admin`: BOOLEAN (Default: False)

## 2. PermissionMatrix (權限矩陣)
- `user_id`: INTEGER (Foreign Key)
- `can_add_order`: BOOLEAN
- `can_transfer_arrival`: BOOLEAN
- `can_transfer_production`: BOOLEAN
- `can_transfer_delivery`: BOOLEAN
- `can_clear_delivery`: BOOLEAN

## 3. SignboardData (看板即時資料表)
- `id`: INTEGER (Primary Key)
- `sequence_id`: TEXT (2位數序號)
- `content`: TEXT
- `current_stage`: TEXT (ORDER / ARRIVAL / PRODUCTION / DELIVERY)
- `order_date`: TEXT
- `arrival_date`: TEXT
- `production_date`: TEXT
- `delivery_date`: TEXT
- `updated_at`: TIMESTAMP

## 4. HistoryLogs (歷史/日誌表)
- `id`: INTEGER (Primary Key)
- `original_sequence_id`: TEXT
- `content`: TEXT
- `timeline`: JSON/TEXT (記錄所有階段階段日期)
- `cleared_by`: INTEGER (User ID)
- `cleared_at`: TIMESTAMP
- `log_year`: INTEGER (用於年度分割查詢)

---
*註：系統將根據 `log_year` 邏輯，在年度結算時將資料物理分割至不同的年度資料庫檔案中（如 `log_2026.sqlite`）。*
