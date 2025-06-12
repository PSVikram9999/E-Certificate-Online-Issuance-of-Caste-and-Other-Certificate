from flask import Flask, render_template, request, redirect, session, send_file, jsonify, flash, url_for
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from models import db, User, Application
import pytesseract
import os
import cv2
import qrcode
import random
import string
from docx import Document
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import fitz  # PyMuPDF
from datetime import timedelta

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'sandbox.smtp.mailtrap.io'
app.config['MAIL_PORT'] = 2525
app.config['MAIL_USERNAME'] = '21ed70500966af'
app.config['MAIL_PASSWORD'] = 'dde127ecef919a'
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

mail = Mail(app)
db.init_app(app)

app.permanent_session_lifetime = timedelta(days=7)

@app.before_request
def make_session_permanent():
    session.permanent = True

os.makedirs("uploads", exist_ok=True)
os.makedirs("certificates", exist_ok=True)

email_token_map = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if not user.is_verified:
                flash("Please verify your email before logging in.", "warning")
                return redirect('/login')
            session['user'] = username
            flash("Login successful!", "success")
            return redirect('/admin' if username == 'admin' else '/choose_certificate')
        flash("Invalid credentials", "danger")
        return redirect('/login')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect('/login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if "@" not in username or len(password) < 8 or not any(char.isdigit() for char in password):
            flash("Enter a valid email and a strong password.", "danger")
            return redirect('/register')
        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect('/register')
        new_user = User(username=username, is_verified=False)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        email_token_map[token] = username
        link = url_for('verify_email', token=token, _external=True)
        msg = Message('Verify Your Email', sender='your_email@gmail.com', recipients=[username])
        msg.body = f'Click to verify your email: {link}'
        mail.send(msg)
        flash('Check your email to verify your account.', 'success')
        return redirect('/login')
    return render_template('register.html')

@app.route('/verify/<token>')
def verify_email(token):
    email = email_token_map.get(token)
    user = User.query.filter_by(username=email).first() if email else None
    if user:
        user.is_verified = True
        db.session.commit()
        flash("Email verified!", "success")
    else:
        flash("Invalid or expired token.", "danger")
    return redirect('/login')

@app.route('/choose_certificate', methods=['GET', 'POST'])
def choose_certificate():
    if 'user' not in session or session['user'] == 'admin':
        return redirect('/login')
    if request.method == 'POST':
        session['certificate_type'] = request.form['certificate_type']
        return redirect('/user')
    return render_template('choose_certificate.html')

@app.route('/user')
def user_portal():
    if 'user' not in session or session['user'] == 'admin':
        return redirect('/login')
    certificate_type = session.get('certificate_type')
    apps = Application.query.filter_by(username=session['user'], certificate_type=certificate_type).all()
    return render_template('user_home.html', applications=apps, user=session['user'], certificate_type=certificate_type)

@app.route('/submit', methods=['POST'])
def submit():
    cert_type = session.get('certificate_type', 'caste')
    data = {
        'certificate_type': cert_type,
        'name': request.form['name'],
        'father_name': request.form['father_name'],
        'phone': request.form['phone'],
        'aadhaar': request.form['aadhaar'],
        'father_aadhaar': request.form['father_aadhaar'],
        'father_cert_id_manual': request.form['father_cert_id_manual'],
        'dob': request.form['dob'],
        'status': 'Pending',
        'username': session['user'],
    }

    # Capture the correct input based on cert_type
    data['caste'] = request.form.get('caste') if cert_type == 'caste' else ""
    data['income'] = request.form.get('income') if cert_type == 'income' else ""

    uploaded = request.files['caste_doc']
    if uploaded:
        filename = secure_filename(uploaded.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        uploaded.save(path)
        text = extract_text_from_file(path)
        data.update(extract_fields_from_text(text, cert_type))
    db.session.add(Application(**data))
    db.session.commit()
    flash("Application submitted!", "success")
    return redirect('/user')

@app.route('/admin')
def admin():
    if 'user' not in session or session['user'] != 'admin':
        return redirect('/login')
    apps = Application.query.all()
    return render_template('admin.html', applications=apps)

@app.route('/approve/<int:index>', methods=['POST'])
def approve(index):
    if 'user' not in session or session['user'] != 'admin':
        return redirect('/login')
    app_obj = Application.query.get(index)
    if not app_obj:
        flash("Not found.", "danger")
        return redirect('/admin')
    app_obj.status = 'Approved'
    app_obj.certificate_id = app_obj.certificate_id or f"CERT-{random.randint(1000,9999)}"
    app_obj.pdf = generate_certificate_pdf(app_obj.__dict__, app_obj.id, app_obj.certificate_type)
    db.session.commit()
    flash("Approved & Certificate Generated.", "success")
    return redirect('/admin')

@app.route('/reject/<int:index>', methods=['POST'])
def reject(index):
    if 'user' not in session or session['user'] != 'admin':
        return redirect('/login')
    app_obj = Application.query.get(index)
    if not app_obj:
        flash("Not found.", "danger")
        return redirect('/admin')
    app_obj.status = 'Rejected'
    db.session.commit()
    flash("Application rejected.", "warning")
    return redirect('/admin')

@app.route('/download/<int:index>')
def download(index):
    if 'user' not in session:
        return redirect('/login')
    app_obj = Application.query.get(index)
    if app_obj and app_obj.pdf and os.path.exists(app_obj.pdf):
        return send_file(app_obj.pdf, as_attachment=True)
    return "PDF not found", 404

# ---------- UTILITIES ----------

def extract_text_from_file(path):
    ext = path.split('.')[-1].lower()
    text = ""
    if ext in ['jpg', 'jpeg', 'png']:
        img = cv2.imread(path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        text = pytesseract.image_to_string(gray)
    elif ext == 'pdf':
        with fitz.open(path) as doc:
            for page in doc:
                text += page.get_text()
    elif ext in ['doc', 'docx']:
        doc = Document(path)
        text = "\n".join([p.text for p in doc.paragraphs])
    return text

def extract_fields_from_text(text, cert_type):
    fields = {'ocr_name': '', 'certificate_id': ''}
    if cert_type == 'caste':
        fields['ocr_caste'] = ''
    else:
        fields['ocr_income'] = ''
    for line in text.split('\n'):
        line = line.strip().lower()
        if 'name' in line and 'father' not in line and 'mother' not in line and ':' in line:
            fields['ocr_name'] = line.split(':')[-1].strip().title()
        elif cert_type == 'caste' and 'caste' in line and ':' in line:
            fields['ocr_caste'] = line.split(':')[-1].strip().title()
        elif cert_type == 'income' and 'income' in line and ':' in line:
            fields['ocr_income'] = line.split(':')[-1].strip().title()
        elif 'certificate' in line and 'id' in line and ':' in line:
            fields['certificate_id'] = line.split(':')[-1].strip().upper()
    return fields

def generate_certificate_pdf(application, index, cert_type):
    path = f"certificates/{cert_type}_certificate_{index}.pdf"
    qr_path = f"certificates/qr_{index}.png"
    cert_id = application.get('certificate_id') or f"CERT-{random.randint(1000,9999)}"
    label = "Caste" if cert_type == 'caste' else "Income"
    value = application.get('caste') if cert_type == 'caste' else application.get('income')

    qr_data = f"""
Certificate ID: {cert_id}
Name: {application['name']}
{label}: {value}
DOB: {application['dob']}
Status: Approved
""".strip()
    qrcode.make(qr_data).save(qr_path)
    c = canvas.Canvas(path, pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(150, 800, f"Government of INDIA - {label} Certificate")
    y = 750
    for label_txt, value in [
        ("Name", application['name']),
        ("Father's Name", application['father_name']),
        ("DOB", application['dob']),
        (label, value),
        ("Certificate ID", cert_id)
    ]:
        c.setFont("Helvetica", 12)
        c.drawString(100, y, f"{label_txt}: {value}")
        y -= 30
    c.drawImage(qr_path, 400, 640, width=100, height=100)
    c.save()
    return path

# ---------- MAIN ----------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', is_verified=True)
            admin.set_password('admin')
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin created: admin / admin")
    app.run(debug=True)