import os, json
from datetime import datetime
from datetime import date
from decimal import Decimal
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
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
    total_price = db.Column(db.Numeric(10, 2))
    is_paid = db.Column(db.Boolean, nullable=True, default=False)
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


class RevenueRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(
        db.Integer, db.ForeignKey("prescription.id"), nullable=False
    )
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date())
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    total_cost = db.Column(db.Numeric(10, 2), nullable=False)
    revenue = db.Column(db.Numeric(10, 2), nullable=False)

    prescription = db.relationship(
        "Prescription", backref=db.backref("revenue_record", uselist=False)
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


@app.route("/", methods=["GET"])
@login_required
def index():
    # 读取 doctor 页面提交的 ?phone_last4=xxxx
    phone_last4 = request.args.get("phone_last4", "").strip()
    if phone_last4:
        patients = Patient.query.filter(Patient.phone.endswith(phone_last4)).all()
    else:
        patients = Patient.query.all()
    return render_template(
        "index.html",
        patients=patients,
        phone_last4=phone_last4,  # 方便 index.html 如果想保留输入值
    )


@app.route("/create_medical_record", methods=["GET", "POST"])
@login_required
def create_medical_record():
    if request.method == "POST":
        patient_id = request.form["patient_id"]
        record_time_str = request.form["record_time"]
        gender = request.form["gender"]
        medical_history = request.form["medical_history"]
        record_time = datetime.strptime(record_time_str, "%Y-%m-%dT%H:%M")
        patient = Patient.query.get(patient_id)
        if patient:
            new_record = MedicalRecord(
                patient_id=patient.id,
                record_time=record_time,
                name=patient.name,
                age=patient.age,
                gender=gender,
                medical_history=medical_history,
            )
            db.session.add(new_record)
            db.session.commit()
            flash("诊疗记录已成功创建！", "success")
            return redirect(url_for("index"))
        else:
            flash("未找到患者信息！", "error")

    patients = Patient.query.all()
    return render_template("create_medical_record.html", patients=patients)


@app.route("/create_prescription", methods=["GET", "POST"])
@login_required
def create_prescription():
    if request.method == "POST":
        patient_id = request.form["patient_id"]
        prescription_time_str = request.form["prescription_time"]
        prescription_time = datetime.strptime(prescription_time_str, "%Y-%m-%dT%H:%M")
        patient = Patient.query.get(patient_id)
        if patient:
            new_prescription = Prescription(
                patient_id=patient.id,
                prescription_time=prescription_time,
                name=patient.name,
                age=patient.age,
            )
            db.session.add(new_prescription)
            db.session.commit()
            items_data = request.form.getlist("drug_name")
            for i in range(len(items_data)):
                drug_name = items_data[i]
                dosage = request.form.getlist("dosage")[i]
                unit = request.form.getlist("unit")[i]
                packaging = request.form.getlist("packaging")[i]
                quantity = request.form.getlist("quantity")[i]

                new_item = PrescriptionItem(
                    prescription_id=new_prescription.id,
                    drug_name=drug_name,
                    dosage=dosage,
                    unit=unit,
                    packaging=packaging,
                    quantity=quantity,
                )
                db.session.add(new_item)
            total = Decimal("0.00")
            for item in new_prescription.items:
                drug = Drug.query.filter_by(name=item.drug_name).first()
            if drug:
                qty = int(item.quantity)
                price = Decimal(drug.price)  # 确保 price 是 Decimal
                total += price * qty
            new_prescription.total_price = total
            db.session.commit()
            flash("处方已保存，总价：" + str(total), "success")
            return redirect(url_for("index"))
        else:
            flash("未找到患者信息！", "error")

    patients = Patient.query.all()
    drugs = Drug.query.all()  # 新增
    drug_info = {
        drug.name: {
            "dosage": float(drug.dosage),
            "unit": drug.drug_unit,
            "packaging": drug.dosage_unit,
        }
        for drug in drugs
    }
    drug_info_json = json.dumps(drug_info, ensure_ascii=False)
    # 接收 copy_from
    copy_from = request.args.get("copy_from", type=int)
    copy_items = []
    if copy_from:
        orig = Prescription.query.get(copy_from)
        if orig:
            for it in orig.items:
                copy_items.append(
                    {
                        "drug_name": it.drug_name,
                        "dosage": float(it.dosage),
                        "unit": it.unit,
                        "quantity": it.quantity,
                        "packaging": it.packaging,
                    }
                )

    return render_template(
        "create_prescription.html",
        patients=patients,
        drugs=drugs,
        drug_info=drug_info_json,
        copy_items=copy_items,
    )


@app.route("/add_patient", methods=["GET", "POST"])
def add_patient():
    if request.method == "POST":
        name = request.form["name"]
        age = request.form["age"]
        phone = request.form["phone"]
        id_card = request.form["id_card"]

        new_patient = Patient(name=name, age=age, phone=phone, id_card=id_card)
        db.session.add(new_patient)
        db.session.commit()

        flash("患者档案已成功创建！", "success")
        return redirect(url_for("index"))

    return render_template("add_patient.html")


@app.route("/view_all_medical_records")
@login_required
def view_all_medical_records():
    records = MedicalRecord.query.all()
    return render_template(
        "medical_records.html", medical_records=records, patient=None
    )


# 某患者病历
@app.route("/patient/<int:patient_id>/medical_records")
@login_required
def view_patient_medical_records(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    records = MedicalRecord.query.filter_by(patient_id=patient_id).all()
    return render_template(
        "medical_records.html", medical_records=records, patient=patient
    )


# 全部处方
@app.route("/view_all_prescriptions")
@login_required
def view_all_prescriptions():
    prescs = Prescription.query.all()
    return render_template("prescriptions.html", prescriptions=prescs, patient=None)


# 某患者处方
@app.route("/patient/<int:patient_id>/prescriptions")
@login_required
def view_patient_prescriptions(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    prescs = Prescription.query.filter_by(patient_id=patient_id).all()
    return render_template("prescriptions.html", prescriptions=prescs, patient=patient)


@app.route("/medical_record/<int:record_id>/edit", methods=["GET", "POST"])
@login_required
def edit_medical_record(record_id):
    record = MedicalRecord.query.get_or_404(record_id)

    # 可选：只允许医生修改
    if current_user.role != "doctor":
        return "无权限访问", 403

    if request.method == "POST":
        # 获取表单中的新病史
        new_history = request.form.get("medical_history", "").strip()
        if not new_history:
            flash("病史内容不能为空", "danger")
        else:
            record.medical_history = new_history
            # 更新诊疗时间为现在
            record.record_time = datetime.utcnow()
            db.session.commit()
            flash("病史已更新", "success")
            # 返回到该患者的病历列表
            return redirect(
                url_for("view_patient_medical_records", patient_id=record.patient_id)
            )

    return render_template("edit_medical_record.html", record=record)


@app.route("/prescription/<int:prescription_id>/detail")
@login_required
def prescription_detail(prescription_id):
    pres = Prescription.query.get_or_404(prescription_id)
    items = [
        {
            "drug_name": item.drug_name,
            "dosage": float(item.dosage),
            "unit": item.unit,
            "quantity": item.quantity,
            "packaging": item.packaging,
        }
        for item in pres.items
    ]
    return jsonify(
        {
            "id": pres.id,
            "patient_name": pres.patient.name,
            "prescription_time": pres.prescription_time.strftime("%Y-%m-%d %H:%M"),
            "total_price": float(pres.total_price) if pres.total_price else 0,
            "items": items,
        }
    )


@app.route("/cashier/charge", methods=["GET"])
@login_required
def cashier_charge():
    if current_user.role != "cashier":
        return "无权限访问", 403
    # 查询 is_paid 为 False 或 NULL 的处方
    prescs = Prescription.query.filter(
        (Prescription.is_paid == False) | (Prescription.is_paid.is_(None))
    ).all()
    return render_template("cashier_charge.html", prescriptions=prescs)


@app.route("/cashier/charge/<int:prescription_id>", methods=["POST"])
@login_required
def cashier_charge_do(prescription_id):
    if current_user.role != "cashier":
        return "无权限访问", 403
    pres = Prescription.query.get_or_404(prescription_id)
    if pres.is_paid:
        flash(f"处方 #{prescription_id} 已标记为已缴费", "info")
        return redirect(url_for("cashier_charge"))

    # 标记已支付
    pres.is_paid = True

    # 计算总成本
    total_cost = Decimal("0.00")
    for item in pres.items:
        drug = Drug.query.filter_by(name=item.drug_name).first()
        if drug:
            total_cost += Decimal(drug.cost) * item.quantity

    # 收入 = 总价 - 总成本
    revenue_amount = pres.total_price - total_cost

    # 写入对账表
    record = RevenueRecord(
        prescription_id=pres.id,
        date=pres.prescription_time.date(),
        total_price=pres.total_price,
        total_cost=total_cost,
        revenue=revenue_amount,
    )
    db.session.add(record)
    db.session.commit()

    flash(f"处方 #{pres.id} 标记为已缴费，收入：{revenue_amount}", "success")
    return redirect(url_for("cashier_charge"))


@app.route("/nurse/prescriptions", methods=["GET", "POST"])
@login_required
def nurse_prescriptions():
    if current_user.role != "nurse":
        return "无权限访问", 403

    # 支持 GET 和 POST 获取表单/查询参数
    phone_last4 = request.values.get("phone_last4", "").strip()
    today_only = request.values.get("today_only", "") == "1"

    # 基础查询，关联 Patient
    query = Prescription.query.join(Patient)

    # 按手机号后四位过滤
    if phone_last4:
        query = query.filter(Patient.phone.endswith(phone_last4))

    # 按日期过滤“仅今天”
    if today_only:
        today = date.today()
        query = query.filter(db.func.date(Prescription.prescription_time) == today)

    # 如果既未搜索，也未勾选“仅今天”，显示所有处方
    prescs = query.all()
    return render_template(
        "nurse_prescriptions.html",
        prescriptions=prescs,
        phone_last4=phone_last4,
        today_only=today_only,
    )


@app.route("/cashier/reconciliation", methods=["GET"])
@login_required
def cashier_reconciliation():
    if current_user.role != "cashier":
        return "无权限访问", 403
    today = date.today()
    total_receivable = db.session.query(func.sum(RevenueRecord.total_price)).filter(
        RevenueRecord.date == today
    ).scalar() or Decimal("0.00")
    return render_template(
        "cashier_reconciliation.html", date=today, total_receivable=total_receivable
    )


@app.route("/inventory/reconciliation", methods=["GET"])
@login_required
def inventory_reconciliation():
    if current_user.role != "inventory":
        return "无权限访问", 403
    today = date.today()
    # 当天应收账款（总价）
    total_receivable = db.session.query(func.sum(RevenueRecord.total_price)).filter(
        RevenueRecord.date == today
    ).scalar() or Decimal("0.00")
    # 当天利润
    total_profit = db.session.query(func.sum(RevenueRecord.revenue)).filter(
        RevenueRecord.date == today
    ).scalar() or Decimal("0.00")
    return render_template(
        "inventory_reconciliation.html",
        date=today,
        total_receivable=total_receivable,
        total_profit=total_profit,
    )


if __name__ == "__main__":
    app.run(
        host=cfg.get("host", "0.0.0.0"),
        port=cfg.get("port", 5000),
        debug=cfg.get("debug", False),
    )
