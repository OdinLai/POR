Created At: 2026-05-02T17:18:43Z
Completed At: 2026-05-02T17:25:00Z
# POR 視覺外掛 (skins) 架構重構任務

- [x] **Phase 1: 基礎架構重構 (Foundation Refactoring)**
    - [x] 建立 `PORsystem/plugins/skins/static/css/base.css` (id: 1)
    - [x] 提取所有皮膚共用的佈局邏輯至 `base.css` (id: 2)
    - [x] 定義標準化的 CSS 變數系統 (Design Tokens) (id: 3)
- [x] **Phase 2: 皮膚文件淨化 (Skin File Purification)**
    - [x] 淨化 `glassmorphism.css` (id: 4)
    - [x] 淨化 `cyberpunk.css` (id: 5)
    - [x] 淨化 `midnight-gold.css` (id: 6)
    - [x] 淨化 `forest-zen.css` (id: 7)
    - [x] 淨化 `paper-white.css` (id: 8)
    - [x] 淨化 `linear-app.css` (id: 9)
- [x] **Phase 3: 路由整合 (Route Integration)**
    - [x] 修改 `routes.py` 中的 `style_css` 路由，實現 `base.css` 與主題 CSS 的動態合併 (id: 10)
- [x] **Phase 4: 驗證與測試 (Verification)**
    - [x] 驗證各皮膚視覺是否與重構前一致 (id: 11)
    - [x] 測試 CSS 變數系統的擴充性 (id: 12)
    - [x] 修正安全性白名單與效能快取機制 (Ruri 審查建議) (id: 13)
- [x] **Phase 5: 插件重命名 (Plugin Renaming)**
    - [x] 將 `od_skin` 重命名為 `skins` (id: 14)

---
會話存檔紀錄：b26db8b1-e28b-4e88-885f-f9dfa32ec4f8
