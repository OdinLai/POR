import os
import configparser
from datetime import timedelta
from flask import Blueprint, request, redirect, session, render_template, current_app
from werkzeug.security import check_password_hash
from models import User

# 定義 Blueprint 與外掛資訊
blueprint = Blueprint('screen_lock', __name__, url_prefix='/screen_lock', template_folder='templates')
PLUGIN_NAME = '看板密碼鎖'
PLUGIN_ICON = '🧩'
PLUGIN_COLOR_CLASS = 'btn-red'

def get_plugin_config():
    """讀取插件專屬的 config.inf 設定檔"""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'config.inf')
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
    return config

@blueprint.before_app_request
def enforce_password():
    """
    全域攔截器：當存取看板主頁面 (/show) 時，
    若插件已啟用且 session 中未標記解鎖狀態，強制引導至解鎖登入頁。
    """
    if request.endpoint == 'show_page':
        config = get_plugin_config()
        is_enabled = config.getboolean('Main', 'enabled', fallback=True)
        
        if is_enabled and not session.get('show_unlocked'):
            return redirect('/screen_lock/login')

@blueprint.route('/')
def index():
    """外掛主頁面：顯示當前運行狀態與控制開關"""
    config = get_plugin_config()
    is_enabled = config.getboolean('Main', 'enabled', fallback=True)
    mode = config.get('Security', 'session_mode', fallback='0')
    
    status_text = "模式 0 (瀏覽器生命週期) 運行中"
    if mode == '1':
        days = config.get('Security', 'session_days', fallback='30')
        status_text = f"模式 1 (長效記憶: {days}天) 運行中..."
    elif mode == '2':
        hours = config.get('Security', 'session_hours', fallback='12')
        status_text = f"模式 2 (短效記憶: {hours}時) 運行中..."
        
    return render_template('lock_status.html', status_text=status_text, is_enabled=is_enabled)


@blueprint.route('/toggle', methods=['POST'])
def toggle_plugin():
    """切換插件啟用狀態"""
    is_enabled = request.form.get('enabled') == 'true'
    
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'config.inf')
    config.read(config_path, encoding='utf-8')
    
    if 'Main' not in config:
        config.add_section('Main')
    config.set('Main', 'enabled', str(is_enabled))
    
    with open(config_path, 'w', encoding='utf-8') as f:
        config.write(f)
        
    return {"status": "success", "enabled": is_enabled}


@blueprint.route('/login', methods=['GET', 'POST'])
def locker_login():
    """
    解鎖驗證路由：提供與原生系統一致的登入介面，
    並根據插件設定檔決定 Session 的有效期限。
    """
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # 查詢使用者並驗證密碼
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            
            # 讀取插件設定決定留存模式
            config = get_plugin_config()
            mode = config.get('Security', 'session_mode', fallback='0')
            
            if mode == '1':
                # 模式 1: 長效記憶 (天數)
                days = int(config.get('Security', 'session_days', fallback='30'))
                current_app.permanent_session_lifetime = timedelta(days=days)
                session.permanent = True
            elif mode == '2':
                # 模式 2: 短效記憶 (小時)
                hours = int(config.get('Security', 'session_hours', fallback='12'))
                current_app.permanent_session_lifetime = timedelta(hours=hours)
                session.permanent = True
            else:
                # 模式 0: 瀏覽器預設 (隨瀏覽器關閉而失效)
                session.permanent = False
            
            # 標記解鎖狀態
            session['show_unlocked'] = True
            return redirect('/show')
        else:
            error = '帳號或密碼錯誤，請重新輸入'
                
    return render_template('lock_login.html', error=error)
