from flask import Blueprint, send_file, request, redirect, url_for, render_template, Response
import os
import configparser

# 插件基本資訊
PLUGIN_NAME = "視覺風格"
PLUGIN_ICON = "🧩"
PLUGIN_COLOR_CLASS = "btn-red"

blueprint = Blueprint('od_skin', __name__, 
                      url_prefix='/od_skin',
                      template_folder='templates',
                      static_folder='static')

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
    available_styles = [
        'classic', 'glassmorphism', 'linear-app', 'cyberpunk', 
        'midnight-gold', 'forest-zen', 'paper-white'
    ]
    return render_template('od_skin_settings.html', 
                           current_style=current_style, 
                           available_styles=available_styles)

@blueprint.route('/update_style', methods=['POST'])
def update_style():
    new_style = request.form.get('style')
    if new_style:
        save_plugin_config(new_style)
    return redirect('/show')

@blueprint.route('/style.css')
def style_css():
    config = get_plugin_config()
    style_name = config.get('Plugin', 'style', fallback='glassmorphism')
    
    if style_name == 'classic':
        return Response("/* Classic Mode: No Override */", mimetype='text/css')
        
    style_path = os.path.join(os.path.dirname(__file__), 'static', 'css', 'styles', f'{style_name}.css')
    
    if not os.path.exists(style_path):
        return Response(f"/* Style {style_name} not found */", mimetype='text/css')
    
    with open(style_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    response = Response(content, mimetype='text/css')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response
