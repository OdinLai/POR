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
    """權限矩陣：二維表格的實體化"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    can_add_order = db.Column(db.Boolean, default=False)        # 新增訂貨
    can_transfer_arrival = db.Column(db.Boolean, default=False)  # 轉移至到貨
    can_transfer_production = db.Column(db.Boolean, default=False) # 轉移至製作
    can_transfer_delivery = db.Column(db.Boolean, default=False)   # 轉移至出庫
    can_clear_delivery = db.Column(db.Boolean, default=False)      # 清除已出庫

class SignboardItem(db.Model):
    """看板即時資料：負責 Show 頁面的核心顯示"""
    id = db.Column(db.Integer, primary_key=True)
    sequence_id = db.Column(db.String(10))  # 序號 (如 01, 02)
    content = db.Column(db.Text, nullable=False)
    
    # 目前階段: ORDER, ARRIVAL, PRODUCTION, DELIVERY
    current_stage = db.Column(db.String(20), default='ORDER')
    
    # 各階段標記日期 (格式可自定義為 MM/DD)
    order_date = db.Column(db.String(10))
    arrival_date = db.Column(db.String(10))
    production_date = db.Column(db.String(10))
    delivery_date = db.Column(db.String(10))
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class HistoryLog(db.Model):
    """歷史日誌：資料清除後的存檔紀錄"""
    id = db.Column(db.Integer, primary_key=True)
    sequence_id = db.Column(db.String(10))
    content = db.Column(db.Text)
    
    # 完整的生命週期時間線 (JSON 字串)
    timeline = db.Column(db.JSON) 
    
    cleared_by = db.Column(db.String(50)) # 執行清除的用戶名
    cleared_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    log_year = db.Column(db.Integer) # 用於年度分割查詢索引
