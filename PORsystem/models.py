from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    """用戶表：儲存登入與管理資訊"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    # 關聯權限
    permissions = db.relationship('Permission', backref='user', uselist=False, cascade="all, delete-orphan")

class Permission(db.Model):
    """權限矩陣：二維表格的實體化 (已更新為動態 JSON)"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    can_add_order = db.Column(db.Boolean, default=False)        # 新增訂貨 (保留為獨立權限)
    
    # 動態階段權限：儲存如 {"ARRIVAL": true, "PRODUCTION": false, ...}
    stage_perms = db.Column(db.JSON, default={})
    
    can_clear_delivery = db.Column(db.Boolean, default=False)      # 清除最後一階段 (保留為獨立權限)
    can_delete = db.Column(db.Boolean, default=False)              # 刪除資料權限

class SignboardItem(db.Model):
    """看板即時資料：負責 Show 頁面的核心顯示 (已更新為動態 JSON)"""
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    remark = db.Column(db.Text) # 備註 (選填)
    
    # 目前階段 ID (對應 config.inf 中的 Key)
    current_stage = db.Column(db.String(50), default='ORDER')
    
    # 各階段標記日期：儲存如 {"ORDER": "...", "ARRIVAL": "..."}
    # 存儲格式為 ISO 字串，讀取時再轉換
    stage_dates = db.Column(db.JSON, default={})
    
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

class HistoryLog(db.Model):
    """歷史日誌：資料清除後的存檔紀錄"""
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)
    remark = db.Column(db.Text)
    
    # 完整的生命週期時間線 (JSON 字串，現在存儲完整 ISO 格式)
    timeline = db.Column(db.JSON) 
    
    cleared_by = db.Column(db.String(50)) # 執行清除的用戶名
    cleared_at = db.Column(db.DateTime, default=datetime.now)
    
    log_year = db.Column(db.Integer) # 用於年度分割查詢索引

class SystemConfig(db.Model):
    """系統配置：儲存看板標題等設定"""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text)
