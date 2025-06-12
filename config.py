# config.py

import os

class Config:
    SECRET_KEY = 'your-secret-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///site.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    MAIL_SERVER = 'sandbox.smtp.mailtrap.io'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'your-mailtrap-username'
    MAIL_PASSWORD = 'your-mailtrap-password'
    MAIL_DEFAULT_SENDER = 'noreply@example.com'

class ProductionConfig(Config):
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'yourgmail@gmail.com'
    MAIL_PASSWORD = 'your-gmail-app-password'
    MAIL_DEFAULT_SENDER = 'yourgmail@gmail.com'

config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig
}

def get_config():
    env = os.getenv('FLASK_ENV', 'development')
    return config_by_name.get(env, DevelopmentConfig)
