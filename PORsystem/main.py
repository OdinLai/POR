from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from models import db, User, Permission, SignboardItem, HistoryLog, SystemConfig
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
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

def get_workflow_stages():
    """解析 config.inf 中的 stages 字串"""
    stages_str = get_inf_config('Workflow', 'stages', 'ORDER:訂貨,ARRIVAL:到貨,PRODUCTION:製作,DELIVERY:出庫')
    stages = []
    for item in stages_str.split(','):
        if ':' in item:
            key, name = item.strip().split(':')
            stages.append({'key': key.strip(), 'name': name.strip()})
    return stages

def get_initial_stage():
    """獲取初始階段 ID"""
    return get_inf_config('Workflow', 'initial_stage', 'ORDER')

# 原始 format_stay_time 已併入 format_item_date 與 format_stay_time_diff

import socket

def get_lan_ip():
    """獲取真實的區域網路 IP，支援從環境變數或 config.inf 手動覆蓋"""
    ip_source = "None"
    final_ip = "127.0.0.1"

    # 1. 優先從環境變數讀取（由啟動腳本自動注入）
    env_ip = os.environ.get('HOST_IP')
    if env_ip and '.' in env_ip and not env_ip.startswith('$'):
        final_ip = env_ip.strip()
        ip_source = "Environment Variable (HOST_IP)"
    else:
        # 2. 其次從 config.inf 讀取手動設定
        manual_ip = get_inf_config('System', 'manual_ip')
        if manual_ip and manual_ip.strip():
            final_ip = manual_ip.strip()
            ip_source = "config.inf (manual_ip)"
        else:
            try:
                # 3. 最後嘗試自動偵測
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(2)
                s.connect(("8.8.8.8", 80))
                final_ip = s.getsockname()[0]
                s.close()
                ip_source = "Auto-detected (Socket)"
            except Exception as e:
                ip_source = f"Fallback (Error: {str(e)})"
                final_ip = "127.0.0.1"

    print(f"--- IP Detection ---")
    print(f"Source: {ip_source}")
    print(f"Result: {final_ip}")
    print(f"--------------------")
    return final_ip

def format_item_date(dt, date_format, end_dt=None):
    """根據設定決定顯示 原始日期 或 停留時間 (支援計算階段差值)"""
    if not dt: return ""
    if date_format == '1': # 顯示停留時間
        # 如果提供了結束時間，則計算階段內的停留時間；否則計算到現在的總時間
        reference_time = end_dt if end_dt else datetime.now()
        return format_stay_time_diff(dt, reference_time)
    else: # 顯示 MM/DD
        return dt.strftime('%m/%d')

def format_stay_time_diff(start_time, end_time):
    """計算並格式化兩個時間點之間的差值"""
    if not start_time or not end_time: return ""
    delta = end_time - start_time
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0: total_seconds = 0
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
    return {
        'site_title': get_config('site_title', '中國到貨看板系統'),
        'workflow_stages': get_workflow_stages(),
        'undo_mode': get_inf_config('System', 'undo_mode', '1')
    }

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
        perm = Permission(user_id=admin.id, can_add_order=True, can_clear_delivery=True)
        # 初始時給予所有已知階段的轉移權限
        stages = get_workflow_stages()
        perm.stage_perms = {s['key']: True for s in stages}
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
        touch_system_update() # 確保大螢幕看板同步刷新標題
        flash('看板標題已更新')
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
    user = User.query.get(session['user_id'])
    return render_template('admin_home.html', perms=user.permissions)

@app.route('/show')
def show_page():
    """電視看板顯示頁面 (多參數支援)"""
    items = SignboardItem.query.order_by(SignboardItem.id.asc()).all()
    date_format = get_inf_config('Display', 'date_format', '0')
    
    # 預處理顯示內容以適應「日期」與「停留時間」切換
    processed_items = []
    stages = get_workflow_stages()
    stage_keys = [s['key'] for s in stages]
    
    for item in items:
        dates_obj = item.stage_dates or {}
        p_item = {
            'id': item.id,
            'content': item.content,
            'remark': item.remark,
            'current_stage': item.current_stage
        }
        
        # 獲取各階段的時間對象
        stage_times = {}
        for s in stages:
            val = dates_obj.get(s['key'])
            if val:
                dt_str = val.get('date') if isinstance(val, dict) else val
                try:
                    stage_times[s['key']] = datetime.fromisoformat(dt_str)
                except (ValueError, TypeError):
                    stage_times[s['key']] = None
            else:
                stage_times[s['key']] = None

        # 動態填充每個階段的顯示日期，改用「階段差值」邏輯
        for i, s in enumerate(stages):
            sk = s['key']
            dt = stage_times.get(sk)
            if not dt:
                p_item[sk] = ""
                continue
            
            # 判斷是否有「下一階段」的時間作為結束點
            next_dt = None
            if i + 1 < len(stages):
                next_sk = stages[i+1]['key']
                next_dt = stage_times.get(next_sk)
            
            # 使用 format_item_date 計算差值
            p_item[sk] = format_item_date(dt, date_format, end_dt=next_dt)
            
        processed_items.append(p_item)

    # 按照階段分組（僅用於相容舊有邏輯或特定視圖，show.html 主要是用 all_items）
    data = {}
    for sk in stage_keys:
        data[sk] = [i for i in processed_items if i['current_stage'] == sk]
    
    today_date = datetime.now().strftime('%Y/%m/%d')
    refresh_seconds = get_inf_config('System', 'refresh_seconds', '60')
    scroll_speed_ms = get_inf_config('Display', 'scroll_speed_ms', '3000')
    show_qrcode = get_inf_config('Display', 'show_qrcode', '1')
    
    # 使用全域系統變更時間戳進行比較，確保刪除操作也能觸發刷新
    latest_ts = get_config('last_system_update', '0')
    
    return render_template('show.html', 
                          data=data, 
                          all_items=processed_items,
                          today_date=today_date,
                          refresh_seconds=refresh_seconds,
                          scroll_speed_ms=scroll_speed_ms,
                          show_qrcode=show_qrcode,
                          lan_ip=get_lan_ip(),
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
    
    mode = request.args.get('mode', 'normal') # normal 或 undo
    user = User.query.get(session['user_id'])
    items = SignboardItem.query.order_by(SignboardItem.id.asc()).all()
    
    # 權限過濾：如果具備階段轉移、清除、或刪除權限，就是有權限的項目
    # 在 undo 模式下，我們需要判斷「這個項目是否位於我能撤回的下一關」
    return render_template('manage.html', items=items, perms=user.permissions, mode=mode)

# 冗餘路由已由 all_data 統一接管

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
        # 通用轉移邏輯
        stages = get_workflow_stages()
        stage_keys = [s['key'] for s in stages]
        
        if target in stage_keys:
            # 修正判定邏輯：檢查「當前階段」是否擁有轉移權限，或具備管理員身分
            if session.get('is_admin') or (perms.stage_perms and perms.stage_perms.get(item.current_stage)):
                # 更新日期紀錄
                # 更新日期紀錄：同時儲存時間與操作者
                dates_obj = dict(item.stage_dates or {})
                dates_obj[target] = {
                    "date": datetime.now().isoformat(),
                    "user": user.username
                }
                item.stage_dates = dates_obj
                item.current_stage = target
                
                db.session.commit()
                touch_system_update()
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'message': f'您沒有轉移至 {target} 的權限'})
                
        elif target == 'CLEAR' and (session.get('is_admin') or perms.can_clear_delivery):
            # 將時程 JSON 轉換為易讀字串供日誌使用
            timeline_str = ", ".join([f"{k}:{v}" for k, v in (item.stage_dates or {}).items()])
            
            # 1. 寫入資料庫歷史表
            log_year = now_dt.year
            log_db = HistoryLog(
                content=item.content,
                remark=item.remark,
                timeline=item.stage_dates,
                cleared_by=session['username'],
                log_year=log_year
            )
            db.session.add(log_db)
            
            # 2. 同步寫入年度實體日誌檔案 (.txt)
            log_file_path = os.path.join(app.instance_path, f'log_{log_year}.txt')
            with open(log_file_path, 'a', encoding='utf-8') as f:
                log_entry = (
                    f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"內容:{item.content} | 備註:{item.remark or ''} | 時程: {timeline_str} | 操作者: {session['username']}\n"
                )
                f.write(log_entry)

            db.session.delete(item) 
            db.session.commit()
            touch_system_update() 
            return jsonify({'success': True, 'message': '已清除並同步記錄至年度日誌檔案'})
        else:
            return jsonify({'success': False, 'message': '權限不足或非法操作'})
        
        db.session.commit()
        touch_system_update() # 標記異動
        return jsonify({'success': True, 'message': f'已轉移至 {target}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/undo_transfer', methods=['POST'])
def api_undo_transfer():
    """撤銷功能：將項目倒回上一個階段"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '未登入'})
    
    data = request.json
    item_id = data.get('id')
    item = SignboardItem.query.get(item_id)
    if not item:
        return jsonify({'success': False, 'message': '找不到此資料'})
        
    user = User.query.get(session['user_id'])
    perms = user.permissions
    stages = get_workflow_stages()
    stage_keys = [s['key'] for s in stages]
    
    # 找到當前階段的索引
    try:
        curr_idx = stage_keys.index(item.current_stage)
    except ValueError:
        return jsonify({'success': False, 'message': '當前階段異常，無法撤回'})
        
    if curr_idx <= 0:
        return jsonify({'success': False, 'message': '已在最初階段，無法撤回'})
        
    prev_stage = stage_keys[curr_idx - 1]
    
    # 權限檢查：是否擁有「目標階段(前一階段)」的轉移權限
    # 或者是管理員
    undo_mode = get_inf_config('System', 'undo_mode', '1')
    
    can_undo = False
    if session.get('is_admin'):
        can_undo = True
    elif undo_mode == '2': # 依權限開放
        if perms.stage_perms and perms.stage_perms.get(prev_stage):
            can_undo = True
            
    if not can_undo:
        return jsonify({'success': False, 'message': '您沒有撤回至此階段的權限'})
        
    try:
        # 執行撤回：修正階段，並刪除「當前階段」的時間紀錄
        dates_obj = dict(item.stage_dates or {})
        if item.current_stage in dates_obj:
            del dates_obj[item.current_stage]
        
        # 額外補強：如果「目標階段」原本就沒有時間紀錄（可能之前是跳級轉移）
        # 則補上當前時間，確保看板不會出現「無停留時間」的奇妙現象
        if prev_stage not in dates_obj:
            dates_obj[prev_stage] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
        item.stage_dates = dates_obj
        item.current_stage = prev_stage
        
        db.session.commit()
        touch_system_update()
        return jsonify({'success': True, 'message': f'已撤回至 {prev_stage}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/delete_item/<int:item_id>', methods=['POST'])
def api_delete_item(item_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '未登入'})
        
    user = User.query.get(session['user_id'])
    if not user.is_admin and not user.permissions.can_delete:
        return jsonify({'success': False, 'message': '權限不足'})
    
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
    
    user = User.query.get(session['user_id'])
    if not user.is_admin and not user.permissions.can_delete:
        flash('您沒有刪除項目的權限')
        return redirect(url_for('manage_page'))
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
    items = SignboardItem.query.order_by(SignboardItem.id.asc()).all()
    
    stages = get_workflow_stages()
    stage_keys = [s['key'] for s in stages]
    
    processed_items = []
    for item in items:
        # 手動處理每個項目的階段數據，支援新舊格式
        p_item = {
            'id': item.id,
            'content': item.content,
            'remark': item.remark,
            'current_stage_name': item.current_stage, # 預設
            'history': []
        }
        
        # 尋找當前階段的顯示名稱
        for s in stages:
            if s['key'] == item.current_stage:
                p_item['current_stage_name'] = s['name']
                break
        
        # 填充歷史紀錄 (排除 CREATED，對應使用者要求「移除新增」)
        dates_obj = item.stage_dates or {}
        for s in stages:
            dt_str = dates_obj.get(s['key'])
            if dt_str:
                # 兼容格式
                if isinstance(dt_str, dict):
                    dt_val = dt_str.get('date', '-')
                else:
                    dt_val = dt_str
                
                try:
                    display_time = datetime.fromisoformat(dt_val).strftime('%Y-%m-%d %H:%M')
                except:
                    display_time = dt_val
                
                p_item['history'].append({'name': s['name'], 'val': display_time})
            else:
                p_item['history'].append({'name': s['name'], 'val': '-'})
            
        processed_items.append(p_item)
        
    return render_template('all_data.html', items=processed_items)

# --- 用戶管理 ---

@app.route('/users')
def users_page():
    if not session.get('is_admin'):
        return "權限不足", 403
    users = User.query.all()
    return render_template('users.html', users=users)

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
            p.can_clear_delivery = f'can_clear_{uid}' in request.form
            p.can_delete = f'can_delete_{uid}' in request.form
            
            # 動態更新階段權限
            stages = get_workflow_stages()
            new_stage_perms = {}
            for s in stages:
                # 排除第一階段(通常是新增)與最後一個階段(通常是清除)? 
                # 不，這裡應該對應到 UI 生成的 checkbox
                new_stage_perms[s['key']] = f'can_{s["key"]}_{uid}' in request.form
            p.stage_perms = new_stage_perms
            
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
    user = User.query.get(session['user_id'])
    perms = user.permissions
    # 只要是管理員，或者是擁有「新增訂貨」權限的人，都可以進來
    if not user.is_admin and not (perms and perms.can_add_order):
        flash('權限不足')
        return redirect(url_for('admin_home'))
    return render_template('settings.html', perms=perms)

@app.route('/edit_item/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    """編輯項目內容與備註"""
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user = User.query.get(session['user_id'])
    if not user.is_admin and not (user.permissions and user.permissions.can_add_order):
        flash('您沒有修改項目的權限')
        return redirect(url_for('admin_home'))
    
    item = SignboardItem.query.get(item_id)
    if not item:
        flash('找不到該項目')
        return redirect(url_for('manage_page'))
    
    if request.method == 'POST':
        item.content = request.form.get('content')
        item.remark = request.form.get('remark')
        db.session.commit()
        touch_system_update()
        flash('項目已更新')
        return redirect(url_for('manage_page'))
    
    return render_template('settings.html', item=item, perms=user.permissions)

@app.route('/add_item', methods=['POST'])
def add_item():
    user = User.query.get(session['user_id'])
    if not user.is_admin and not (user.permissions and user.permissions.can_add_order):
        flash('您沒有新增訂單的權限')
        return redirect(url_for('settings_page'))
    
    content = request.form.get('content')
    remark = request.form.get('remark')
    now_dt = datetime.now()
    
    initial_key = get_initial_stage()
    # 儲存新增資訊與第一階段資訊
    user_name = session.get('username', '未知')
    stage_info = {
        "date": now_dt.isoformat(),
        "user": user_name
    }
    item = SignboardItem(
        content=content, 
        remark=remark, 
        current_stage=initial_key, 
        stage_dates={
            "CREATED": stage_info,
            initial_key: stage_info
        }
    )
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
        # 初始化管理員邏輯
        if not User.query.filter_by(username='admin').first():
            admin_pwd = generate_password_hash('888888')
            admin = User(username='admin', password_hash=admin_pwd, is_admin=True)
            db.session.add(admin)
            db.session.commit()
            
            # 給予所有階段權限
            perm = Permission(user_id=admin.id, can_add_order=True, can_clear_delivery=True, can_delete=True)
            stages = get_workflow_stages()
            perm.stage_perms = {s['key']: True for s in stages}
            db.session.add(perm)
            db.session.commit()
            print("後台管理員 (admin) 已初始化")

        # 2. 建立最高管理員 administrator (緊急後門)
        root = User.query.filter_by(username='administrator').first()
        if not root:
            root_pwd = generate_password_hash('03211230')
            root = User(username='administrator', password_hash=root_pwd, is_admin=True)
            db.session.add(root)
            db.session.commit()
            
            perm = Permission(user_id=root.id, can_add_order=True, can_clear_delivery=True, can_delete=True)
            stages = get_workflow_stages()
            perm.stage_perms = {s['key']: True for s in stages}
            db.session.add(perm)
            db.session.commit()
            print("超級管理員 (administrator) 已初始化")
            
    app.run(host='0.0.0.0', port=5000, debug=True)
