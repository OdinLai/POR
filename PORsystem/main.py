from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from models import db, User, Permission, SignboardItem, HistoryLog
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database/projection.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'signboard-secret-key-12345' # 建議之後改為 .env 讀取

# 確保資料夾存在
os.makedirs('database', exist_ok=True)

db.init_app(app)

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
    """電視看板顯示頁面 (30秒刷新)"""
    items = SignboardItem.query.all()
    # 按階段分組
    data = {
        'ORDER': [i for i in items if i.current_stage == 'ORDER'],
        'ARRIVAL': [i for i in items if i.current_stage == 'ARRIVAL'],
        'PRODUCTION': [i for i in items if i.current_stage == 'PRODUCTION'],
        'DELIVERY': [i for i in items if i.current_stage == 'DELIVERY']
    }
    return render_template('show.html', data=data)

@app.route('/manage')
def manage_page():
    """進度管理頁面"""
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user = User.query.get(session['user_id'])
    items = SignboardItem.query.all()
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
    
    now_str = datetime.now().strftime('%m/%d')
    user = User.query.get(session['user_id'])
    perms = user.permissions
    
    try:
        if target == 'ARRIVAL' and perms.can_transfer_arrival:
            item.current_stage = 'ARRIVAL'
            item.arrival_date = now_str
        elif target == 'PRODUCTION' and perms.can_transfer_production:
            item.current_stage = 'PRODUCTION'
            item.production_date = now_str
        elif target == 'DELIVERY' and perms.can_transfer_delivery:
            item.current_stage = 'DELIVERY'
            item.delivery_date = now_str
        elif target == 'CLEAR' and perms.can_clear_delivery:
            # 1. 寫入資料庫歷史表
            log_year = datetime.now().year
            timeline_data = {
                'order': item.order_date,
                'arrival': item.arrival_date,
                'production': item.production_date,
                'delivery': item.delivery_date
            }
            log_db = HistoryLog(
                sequence_id=item.sequence_id,
                content=item.content,
                timeline=timeline_data,
                cleared_by=session['username'],
                log_year=log_year
            )
            db.session.add(log_db)
            
            # 2. 同步寫入年度實體日誌檔案 (.txt)
            log_file_path = f'database/log_{log_year}.txt'
            with open(log_file_path, 'a', encoding='utf-8') as f:
                log_entry = (
                    f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"序號:{item.sequence_id} | 內容:{item.content} | "
                    f"時程: {timeline_data} | 操作者: {session['username']}\n"
                )
                f.write(log_entry)

            db.session.delete(item) 
            db.session.commit()
            return jsonify({'success': True, 'message': '已清除並同步記錄至年度日誌檔案'})
        else:
            return jsonify({'success': False, 'message': '權限不足或非法操作'})
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'已轉移至 {target}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

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

@app.route('/users/delete/<int:id>')
def delete_user(id):
    if not session.get('is_admin'): return "403", 403
    u = User.query.get(id)
    if u and u.username != 'admin':
        db.session.delete(u)
        db.session.commit()
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
    
    seq = request.form.get('sequence_id')
    content = request.form.get('content')
    now_str = datetime.now().strftime('%m/%d')
    
    item = SignboardItem(sequence_id=seq, content=content, current_stage='ORDER', order_date=now_str)
    db.session.add(item)
    db.session.commit()
    flash(f'成功新增序號 {seq}')
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
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin_pwd = generate_password_hash('888888')
            admin = User(username='admin', password_hash=admin_pwd, is_admin=True)
            db.session.add(admin)
            db.session.commit()
            perm = Permission(user_id=admin.id, can_add_order=True, can_transfer_arrival=True, can_transfer_production=True, can_transfer_delivery=True, can_clear_delivery=True)
            db.session.add(perm)
            db.session.commit()
            
    app.run(host='0.0.0.0', port=5000, debug=True)
