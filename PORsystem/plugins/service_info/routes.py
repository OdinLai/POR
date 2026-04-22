from flask import Blueprint, render_template, session, redirect, url_for
from models import db

# 插件元數據 (供主選單動態偵測)
PLUGIN_NAME = "版本與加值服務"
PLUGIN_ICON = "🔖"
PLUGIN_COLOR_CLASS = "btn-azure"

# 建立 Blueprint
blueprint = Blueprint(
    'service_info', 
    __name__, 
    template_folder='templates',
    url_prefix='/service_info'
)

@blueprint.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    # 從環境變數或 config 讀取版本資訊 (此處為示意，可擴充)
    service_data = {
        "version": "v1.5.2-璇璣",
        "release_date": "2026-04-22",
        "plan_name": "核心基礎版 + 雲端備份插件",
        "addons": [
            {"name": "雲端自動備份", "status": "已開通", "price": "1,200/年"},
            {"name": "璇璣動態布告欄", "status": "已開通", "price": "贈送"},
            {"name": "多看板鏈路監控", "status": "未開通", "price": "2,500/年"}
        ],
        "renewal_note": "下次續約日期：2027-04-22。請與「青玉案」官方專線聯繫對價。"
    }
    
    return render_template('service_info.html', service=service_data)
