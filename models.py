from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), db.ForeignKey('user.username'))
    certificate_type = db.Column(db.String(20))  # 'caste' or 'income'

    name = db.Column(db.String(100))
    father_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    aadhaar = db.Column(db.String(20))
    father_aadhaar = db.Column(db.String(20))
    father_cert_id_manual = db.Column(db.String(50))

    caste = db.Column(db.String(50))  # Only for caste certificate
    income = db.Column(db.String(50))  # Only for income certificate

    dob = db.Column(db.String(20))
    status = db.Column(db.String(20), default="Pending")
    pdf = db.Column(db.String(200))
    certificate_id = db.Column(db.String(50))

    # Extracted via OCR
    ocr_name = db.Column(db.String(100))
    ocr_caste = db.Column(db.String(50))
    ocr_income = db.Column(db.String(50))
    ocr_cert_id = db.Column(db.String(50))