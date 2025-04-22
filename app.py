import os, json
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# 加载配置
def load_config():
    with open('config.json', encoding='utf-8') as f:
        return json.load(f)

cfg = load_config()
app = Flask(__name__)
app.config['SECRET_KEY'] = cfg['secret_key']
# SQLite 示例
db_path = os.path.join(os.path.dirname(__file__), cfg.get('db_file', 'clinic.db'))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# —— 用户模型
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # 可用 werkzeug.security 生成 hash
    role = db.Column(db.String(20), nullable=False)     # doctor/nurse/cashier/inventory

# 初始化数据库并创建示例用户（仅开发用）
with app.app_context():
    db.create_all()
    if not User.query.first():
        users = [
            User(username='doc1', password='pass', role='doctor'),
            User(username='nurse1', password='pass', role='nurse'),
            User(username='cash1', password='pass', role='cashier'),
            User(username='inv1', password='pass', role='inventory'),
        ]
        db.session.bulk_save_objects(users)
        db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# —— 登录路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form['username']).first()
        if u and request.form['password'] == u.password:
            login_user(u)
            flash('登录成功', 'success')
            # 根据角色跳转
            return redirect(url_for(u.role + '_page'))
        flash('用户名或密码错误', 'danger')
    return render_template('login.html')

# —— 注销
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# —— 各角色页面
@app.route('/doctor')
@login_required
def doctor_page():
    if current_user.role != 'doctor':
        return "无权限访问", 403
    return render_template('doctor.html')

@app.route('/nurse')
@login_required
def nurse_page():
    if current_user.role != 'nurse':
        return "无权限访问", 403
    return render_template('nurse.html')

@app.route('/cashier')
@login_required
def cashier_page():
    if current_user.role != 'cashier':
        return "无权限访问", 403
    return render_template('cashier.html')

@app.route('/inventory')
@login_required
def inventory_page():
    if current_user.role != 'inventory':
        return "无权限访问", 403
    return render_template('inventory.html')

if __name__ == '__main__':
    app.run(host=cfg.get('host','0.0.0.0'), port=cfg.get('port',5000), debug=cfg.get('debug',False))