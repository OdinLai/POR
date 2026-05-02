from flask import Blueprint, send_file, request, redirect, url_for, render_template, Response
import os
import configparser

# 插件基本資訊
PLUGIN_NAME = "視覺風格"
PLUGIN_ICON = "🧩"
PLUGIN_COLOR_CLASS = "btn-red"

blueprint = Blueprint('skins', __name__, 
                      url_prefix='/skins',
                      template_folder='templates',
                      static_folder='static')

# 可用皮膚白名單
AVAILABLE_STYLES = [
    'classic', 'glassmorphism', 'linear-app', 'cyberpunk', 
    'midnight-gold', 'forest-zen', 'paper-white'
]

# 伺服器端簡易快取
_style_cache = {
    'name': None,
    'content': None
}

def get_plugin_config():
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'config.inf')
    config.read(config_path, encoding='utf-8')
    return config

def save_plugin_config(style):
    config = get_plugin_config()
    if not config.has_section('Plugin'):
        config.add_section('Plugin')
    config.set('Plugin', 'style', style)
    config_path = os.path.join(os.path.dirname(__file__), 'config.inf')
    with open(config_path, 'w', encoding='utf-8') as f:
        config.write(f)

@blueprint.route('/')
def index():
    config = get_plugin_config()
    current_style = config.get('Plugin', 'style', fallback='glassmorphism')
    return render_template('skins_settings.html', 
                           current_style=current_style, 
                           available_styles=AVAILABLE_STYLES)

@blueprint.route('/update_style', methods=['POST'])
def update_style():
    new_style = request.form.get('style')
    # 琉璃審查：加入白名單校驗
    if new_style in AVAILABLE_STYLES:
        save_plugin_config(new_style)
        # 清除快取
        global _style_cache
        _style_cache['name'] = None
    return redirect('/show')

@blueprint.route('/style.css')
def style_css():
    config = get_plugin_config()
    style_name = config.get('Plugin', 'style', fallback='glassmorphism')
    
    if style_name == 'classic':
        return Response("/* Classic Mode: No Override */", mimetype='text/css')
        
    # 琉璃審查：效能優化，優先使用快取
    global _style_cache
    if _style_cache['name'] == style_name and _style_cache['content']:
        response = Response(_style_cache['content'], mimetype='text/css')
        response.headers['Cache-Control'] = 'public, max-age=3600' # 允許瀏覽器緩存 1 小時
        return response

    base_path = os.path.join(os.path.dirname(__file__), 'static', 'css', 'base.css')
    style_path = os.path.join(os.path.dirname(__file__), 'static', 'css', 'styles', f'{style_name}.css')
    
    content = ""
    
    if os.path.exists(base_path):
        with open(base_path, 'r', encoding='utf-8') as f:
            content += f"/* --- Base Framework --- */\n{f.read()}\n"
            
    if os.path.exists(style_path):
        with open(style_path, 'r', encoding='utf-8') as f:
            content += f"\n/* --- Theme: {style_name} --- */\n{f.read()}\n"
    
    if not content:
        return Response(f"/* Style {style_name} not found */", mimetype='text/css')
    
    # 更新快取
    _style_cache['name'] = style_name
    _style_cache['content'] = content
        
    response = Response(content, mimetype='text/css')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response
