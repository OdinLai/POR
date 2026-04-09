from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from models import db, User, Permission, SignboardItem, HistoryLog, SystemConfig
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import func
import configparser

app = Flask(__name__, instance_relative_config=True)
# 確保 instance 資料夾存在
try:
    os.makedirs(app.instance_path, exist_ok=True)
except OSError:
    pass

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'projection.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'signboard-secret-key-12345'

db.init_app(app)

# 輔助函式：獲取系統配置
def get_config(key, default=None):
    config = SystemConfig.query.filter_by(key=key).first()
    return config.value if config else default

def get_inf_config(section, key, default=None):
    """從 config.inf 讀取設定，優先級最高"""
    inf_path = os.path.join(os.path.dirname(__file__), 'config.inf')
    if not os.path.exists(inf_path):
        return default
    config = configparser.ConfigParser()
    try:
        config.read(inf_path, encoding='utf-8')
        if section in config and key in config[section]:
            return config[section][key]
    except Exception:
        pass
    return default

def format_stay_time(start_time):
    """將時間差格式化為 分、時分、天時"""
    if not start_time: return ""
    delta = datetime.now() - start_time
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60: return "剛剛"
    
    minutes = (total_seconds // 60) % 60
    hours = (total_seconds // 3600) % 24
    days = total_seconds // 86400
    
    if days > 0:
        return f"{days}天{hours}時"
    elif hours > 0:
        return f"{hours}時{minutes}分"
    else:
        return f"{minutes}分"

def format_item_date(dt, date_format):
    """根據設定決定顯示 原始日期 或 停留時間"""
    if not dt: return ""
    if date_format == '1': # 顯示停留時間
        return format_stay_time(dt)
    else: # 顯示 MM/DD
        return dt.strftime('%m/%d')

def touch_system_update():
    """標記系統發生了任何形式的資料變動（新增、轉移、刪除）"""
    config = SystemConfig.query.filter_by(key='last_system_update').first()
    now_str = str(datetime.now().timestamp())
    if config:
        config.value = now_str
    else:
        config = SystemConfig(key='last_system_update', value=now_str)
        db.session.add(config)
    db.session.commit()

@app.context_processor
def inject_config():
    # 標題維持從資料庫或預設讀取，不開放外部 .inf 修改以避免衝突
    return {'site_title': get_config('site_title', '中國到貨看板系統')}

# 初始化資料庫
@app.before_first_request
def create_tables():
    db.create_all()
    # 建立預設管理員
    if not User.query.filter_by(username='admin').first():
        admin_pwd = generate_password_hash('888888')
        admin = User(username='admin', password_hash=admin_pwd, is_admin=True)
        db.session.add(admin)
        db.session.commit()
        # 給予全權限
        perm = Permission(user_id=admin.id, 
                          can_add_order=True, 
                          can_transfer_arrival=True, 
                          can_transfer_production=True, 
                          can_transfer_delivery=True, 
                          can_clear_delivery=True)
        db.session.add(perm)
        db.session.commit()

# --- 登入驗證 ---
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('admin_home'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    user = User.query.filter_by(username=username).first()
    
    if user and check_password_hash(user.password_hash, password):
        session['user_id'] = user.id
        session['username'] = user.username
        session['is_admin'] = user.is_admin
        return redirect(url_for('admin_home'))
    
    flash('帳號或密碼錯誤')
    return redirect(url_for('index'))

@app.route('/update_title', methods=['POST'])
def update_title():
    if not session.get('username'):
        return redirect(url_for('login'))
    
    new_title = request.form.get('new_title')
    if new_title:
        config = SystemConfig.query.filter_by(key='site_title').first()
        if not config:
            config = SystemConfig(key='site_title', value=new_title)
            db.session.add(config)
        else:
            config.value = new_title
        db.session.commit()
    return redirect(url_for('manage_page'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- 主要頁面 ---

@app.route('/admin_home')
def admin_home():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('admin_home.html')

@app.route('/show')
def show_page():
    """電視看板顯示頁面 (多參數支援)"""
    items = SignboardItem.query.order_by(SignboardItem.id.asc()).all()
    date_format = get_inf_config('Display', 'date_format', '0')
    
    # 預處理顯示內容以適應「日期」與「停留時間」切換
    processed_items = []
    for item in items:
        p_item = {
            'id': item.id,
            'content': item.content,
            'remark': item.remark,
            'current_stage': item.current_stage,
            'ORDER': format_item_date(item.order_date, date_format),
            'ARRIVAL': format_item_date(item.arrival_date, date_format),
            'PRODUCTION': format_item_date(item.production_date, date_format),
            'DELIVERY': format_item_date(item.delivery_date, date_format)
        }
        processed_items.append(p_item)

    data = {
        'ORDER': [i for i in processed_items if i['current_stage'] == 'ORDER'],
        'ARRIVAL': [i for i in processed_items if i['current_stage'] == 'ARRIVAL'],
        'PRODUCTION': [i for i in processed_items if i['current_stage'] == 'PRODUCTION'],
        'DELIVERY': [i for i in processed_items if i['current_stage'] == 'DELIVERY']
    }
    
    today_date = datetime.now().strftime('%Y/%m/%d')
    refresh_seconds = get_inf_config('System', 'refresh_seconds', '60')
    scroll_speed_ms = get_inf_config('Display', 'scroll_speed_ms', '3000')
    
    # 使用全域系統變更時間戳進行比較，確保刪除操作也能觸發刷新
    latest_ts = get_config('last_system_update', '0')
    
    return render_template('show.html', 
                          data=data, 
                          all_items=processed_items,
                          today_date=today_date,
                          refresh_seconds=refresh_seconds,
                          scroll_speed_ms=scroll_speed_ms,
                          latest_ts=latest_ts)

@app.route('/api/latest_update')
def api_latest_update():
    """供前端輪詢的偵測介面：回傳系統全域變動版本號"""
    try:
        latest_ts = get_config('last_system_update', '0')
        return jsonify({'success': True, 'timestamp': float(latest_ts)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/manage')
def manage_page():
    """進度管理頁面"""
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user = User.query.get(session['user_id'])
    # 這裡也需要按照順序抓取，確保管理端看到的序號跟看板一致
    items = SignboardItem.query.order_by(SignboardItem.id.asc()).all()
    return render_template('manage.html', items=items, perms=user.permissions)

# --- API 與資料操作 ---

@app.route('/api/transfer', methods=['POST'])
def api_transfer():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '未登入'})
    
    data = request.json
    item_id = data.get('id')
    target = data.get('target') # ARRIVAL, PRODUCTION, DELIVERY, CLEAR
    
    item = SignboardItem.query.get(item_id)
    if not item:
        return jsonify({'success': False, 'message': '找不到此資料'})
    
    now_dt = datetime.now()
    user = User.query.get(session['user_id'])
    perms = user.permissions
    
    try:
        if target == 'ARRIVAL' and perms.can_transfer_arrival:
            item.current_stage = 'ARRIVAL'
            item.arrival_date = now_dt
        elif target == 'PRODUCTION' and perms.can_transfer_production:
            item.current_stage = 'PRODUCTION'
            item.production_date = now_dt
        elif target == 'DELIVERY' and perms.can_transfer_delivery:
            item.current_stage = 'DELIVERY'
            item.delivery_date = now_dt
        elif target == 'CLEAR' and perms.can_clear_delivery:
            # 1. 寫入資料庫歷史表 (轉換為 ISO 字串存入 JSON)
            log_year = now_dt.year
            timeline_data = {
                'order': item.order_date.isoformat() if item.order_date else "",
                'arrival': item.arrival_date.isoformat() if item.arrival_date else "",
                'production': item.production_date.isoformat() if item.production_date else "",
                'delivery': item.delivery_date.isoformat() if item.delivery_date else ""
            }
            log_db = HistoryLog(
                content=item.content,
                remark=item.remark,
                timeline=timeline_data,
                cleared_by=session['username'],
                log_year=log_year
            )
            db.session.add(log_db)
            
            # 2. 同步寫入年度實體日誌檔案 (.txt)
            log_file_path = os.path.join(app.instance_path, f'log_{log_year}.txt')
            with open(log_file_path, 'a', encoding='utf-8') as f:
                log_entry = (
                    f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"內容:{item.content} | 備註:{item.remark or ''} | 時程: {timeline_data} | 操作者: {session['username']}\n"
                )
                f.write(log_entry)

            db.session.delete(item) 
            db.session.commit()
            touch_system_update() # 標記異動
            return jsonify({'success': True, 'message': '已清除並同步記錄至年度日誌檔案'})
        else:
            return jsonify({'success': False, 'message': '權限不足或非法操作'})
        
        db.session.commit()
        touch_system_update() # 標記異動
        return jsonify({'success': True, 'message': f'已轉移至 {target}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/delete_item/<int:item_id>', methods=['POST'])
def api_delete_item(item_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '未登入'})
    
    item = SignboardItem.query.get(item_id)
    if not item:
        return jsonify({'success': False, 'message': '找不到該項目'})
    
    try:
        db.session.delete(item)
        db.session.commit()
        touch_system_update() # 標記異動，確保看板同步刷新
        return jsonify({'success': True, 'message': '項目已刪除'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/manage/delete/<int:item_id>', methods=['POST'])
def manage_delete_item(item_id):
    if 'user_id' not in session: return "403", 403
    item = SignboardItem.query.get(item_id)
    if item:
        try:
            db.session.delete(item)
            db.session.commit()
            flash('項目已成功刪除')
        except Exception as e:
            db.session.rollback()
            flash(f'刪除失敗: {str(e)}')
    return redirect(url_for('manage_page'))

@app.route('/all_data')
def all_data():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    items = SignboardItem.query.all()
    return render_template('all_data.html', items=items)

# --- 用戶管理 ---

@app.route('/users')
def users_page():
    if not session.get('is_admin'):
        return "權限不足", 403
    users = User.query.all()
    return render_template('users.html', users=users)

@app.route('/users/add', methods=['POST'])
def add_user():
    if not session.get('is_admin'): return "403", 403
    username = request.form.get('username')
    user = User(username=username, password_hash=generate_password_hash('666666'))
    db.session.add(user)
    db.session.commit()
    perm = Permission(user_id=user.id)
    db.session.add(perm)
    db.session.commit()
    return redirect(url_for('users_page'))

@app.route('/users/update_permissions', methods=['POST'])
def update_permissions():
    if not session.get('is_admin'): return "403", 403
    user_ids = request.form.getlist('user_id')
    for uid in user_ids:
        u = User.query.get(uid)
        if u and u.username != 'admin':
            u.is_admin = f'is_admin_{uid}' in request.form
            p = u.permissions
            p.can_add_order = f'can_add_{uid}' in request.form
            p.can_transfer_arrival = f'can_arrival_{uid}' in request.form
            p.can_transfer_production = f'can_production_{uid}' in request.form
            p.can_transfer_delivery = f'can_delivery_{uid}' in request.form
            p.can_clear_delivery = f'can_clear_{uid}' in request.form
    db.session.commit()
    flash('權限已更新')
    return redirect(url_for('users_page'))

@app.route('/users/delete/<int:id>', methods=['POST'])
def delete_user(id):
    if not session.get('is_admin'): return "403", 403
    u = User.query.get(id)
    if u:
        if u.username == 'admin':
            flash('無法刪除超級管理員')
        else:
            try:
                # 顯式清理關聯物件
                if u.permissions:
                    db.session.delete(u.permissions)
                db.session.delete(u)
                db.session.commit()
                flash(f'用戶 {u.username} 已刪除')
            except Exception as e:
                db.session.rollback()
                flash(f'刪除失敗: {str(e)}')
    return redirect(url_for('users_page'))

# --- 資料新增 ---

@app.route('/settings')
def settings_page():
    if 'user_id' not in session: return redirect(url_for('index'))
    return render_template('settings.html')

@app.route('/add_item', methods=['POST'])
def add_item():
    user = User.query.get(session['user_id'])
    if not user.permissions.can_add_order:
        flash('您沒有新增訂單的權限')
        return redirect(url_for('settings_page'))
    
    content = request.form.get('content')
    remark = request.form.get('remark')
    now_dt = datetime.now()
    
    item = SignboardItem(content=content, remark=remark, current_stage='ORDER', order_date=now_dt)
    db.session.add(item)
    db.session.commit()
    touch_system_update() # 標記新項目加入
    flash(f'成功新增一筆資料')
    return redirect(url_for('settings_page'))

# --- 修改密碼 ---
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session: return redirect(url_for('index'))
    if request.method == 'POST':
        new_pwd = request.form.get('password')
        user = User.query.get(session['user_id'])
        user.password_hash = generate_password_hash(new_pwd)
        db.session.commit()
        flash('密碼已修改')
        return redirect(url_for('admin_home'))
    return render_template('change_password.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # 初始化管理員邏輯 (同前)
        if not User.query.filter_by(username='admin').first():
            admin_pwd = generate_password_hash('888888')
            admin = User(username='admin', password_hash=admin_pwd, is_admin=True)
            db.session.add(admin)
            db.session.commit()
            perm = Permission(user_id=admin.id, can_add_order=True, can_transfer_arrival=True, can_transfer_production=True, can_transfer_delivery=True, can_clear_delivery=True)
            db.session.add(perm)
            db.session.commit()
            
    app.run(host='0.0.0.0', port=5000, debug=True)
