import os, json
from decimal import Decimal
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)


# 加载配置
def load_config():
    with open("config.json", encoding="utf-8") as f:
        return json.load(f)


cfg = load_config()
app = Flask(__name__)
app.config["SECRET_KEY"] = cfg["secret_key"]
# SQLite 示例
db_path = os.path.join(os.path.dirname(__file__), cfg.get("db_file", "clinic.db"))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


# —— 用户模型
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(
        db.String(200), nullable=False
    )  # 可用 werkzeug.security 生成 hash
    role = db.Column(db.String(20), nullable=False)  # doctor/nurse/cashier/inventory


# —— 药品模型
class Drug(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    brand = db.Column(db.String(100), nullable=False)  # 品牌
    dosage = db.Column(db.Float, nullable=False)
    drug_unit = db.Column(db.String(20), nullable=False)
    dosage_unit = db.Column(db.String(20), nullable=False)  # 片、盒、支等
    quantity = db.Column(db.Integer, default=0)
    price = db.Column(db.Numeric(10, 2), nullable=False)  # 售价
    cost = db.Column(db.Numeric(10, 2), nullable=False)  # 成本


class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    id_card = db.Column(db.String(18), unique=True, nullable=False)


# 病历表
class MedicalRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), nullable=False)
    record_time = db.Column(db.DateTime, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    medical_history = db.Column(db.Text, nullable=False)
    patient = db.relationship(
        "Patient", backref=db.backref("medical_records", lazy=True)
    )


# 处方表
class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), nullable=False)
    prescription_time = db.Column(db.DateTime, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    patient = db.relationship("Patient", backref=db.backref("prescriptions", lazy=True))


# 处方项目表
class PrescriptionItem(db.Model):
    prescription_item_id = db.Column(
        db.Integer, primary_key=True
    )  # 处方项目 ID，作为主键
    prescription_id = db.Column(
        db.Integer, db.ForeignKey("prescription.id"), nullable=False
    )
    drug_name = db.Column(db.String(100), nullable=False)
    dosage = db.Column(db.Numeric(10, 2), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    packaging = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    prescription = db.relationship(
        "Prescription", backref=db.backref("items", lazy=True)
    )


# 初始化数据库并创建示例用户（仅开发用）
with app.app_context():
    db.create_all()
    if not User.query.first():
        users = [
            User(username="doc1", password="pass", role="doctor"),
            User(username="nurse1", password="pass", role="nurse"),
            User(username="cash1", password="pass", role="cashier"),
            User(username="inv1", password="pass", role="inventory"),
        ]
        db.session.bulk_save_objects(users)
        db.session.commit()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# —— 登录路由
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(username=request.form["username"]).first()
        if u and request.form["password"] == u.password:
            login_user(u)
            flash("登录成功", "success")
            # 根据角色跳转
            return redirect(url_for(u.role + "_page"))
        flash("用户名或密码错误", "danger")
    return render_template("login.html")


# —— 注销
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# —— 各角色页面
@app.route("/doctor")
@login_required
def doctor_page():
    if current_user.role != "doctor":
        return "无权限访问", 403
    return render_template("doctor.html")


@app.route("/nurse")
@login_required
def nurse_page():
    if current_user.role != "nurse":
        return "无权限访问", 403
    return render_template("nurse.html")


@app.route("/cashier")
@login_required
def cashier_page():
    if current_user.role != "cashier":
        return "无权限访问", 403
    return render_template("cashier.html")


@app.route("/inventory")
@login_required
def inventory_page():
    if current_user.role != "inventory":
        return "无权限访问", 403
    return render_template("inventory.html")


@app.route("/inventory/drugs")
@login_required
def inventory_drugs():
    if current_user.role != "inventory":
        return "无权限访问", 403
    drugs = Drug.query.all()
    return render_template("inventory_drugs.html", drugs=drugs)


@app.route("/inventory/new", methods=["GET", "POST"])
@login_required
def new_drug():
    if current_user.role != "inventory":
        return "无权限访问", 403
    if request.method == "POST":
        drug = Drug(
            id=request.form["id"],
            name=request.form["name"],
            brand=request.form["brand"],
            dosage=float(request.form["dosage"]),
            drug_unit=request.form["drug_unit"],
            dosage_unit=request.form["dosage_unit"],
            quantity=int(request.form["quantity"]),
            price=Decimal(request.form["price"]),
            cost=Decimal(request.form["cost"]),
        )
        db.session.add(drug)
        db.session.commit()
        return redirect(url_for("inventory_drugs"))
    return render_template("new_drug.html")


# —— 库管：库存增减
@app.route("/inventory/adjust/<int:drug_id>", methods=["POST"])
@login_required
def adjust_drug(drug_id):
    if current_user.role != "inventory":
        return "无权限访问", 403
    delta = int(request.form["delta"])
    drug = Drug.query.filter_by(id=drug_id).first_or_404()
    if drug is None:
        flash("药品不存在", "danger")
        return redirect(url_for("inventory_drugs"))
    if delta < 0 and abs(delta) > drug.quantity:
        flash(f"{drug.name}库存不足", "danger")
        return redirect(url_for("inventory_drugs"))
    # 更新库存
    drug.quantity = max(drug.quantity + delta, 0)
    db.session.commit()
    flash(f"{drug.name}库存已调整 {delta:+d}", "success")
    return redirect(url_for("inventory_drugs"))


# —— 库管：删除药品
@app.route("/inventory/delete/<int:drug_id>", methods=["POST"])
@login_required
def delete_drug(drug_id):
    if current_user.role != "inventory":
        return "无权限访问", 403
    drug = Drug.query.get_or_404(drug_id)
    db.session.delete(drug)
    db.session.commit()
    flash(f"已删除药品 “{drug.name}”", "success")
    return redirect(url_for("inventory_drugs"))


if __name__ == "__main__":
    app.run(
        host=cfg.get("host", "0.0.0.0"),
        port=cfg.get("port", 5000),
        debug=cfg.get("debug", False),
    )
