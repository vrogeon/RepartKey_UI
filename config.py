# config.py - Configuration centralisée pour RepartKey

import os
from datetime import timedelta

class Config:
    """Configuration de base"""
    
    # Chemins
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # Base de données
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "repartkey.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Sécurité
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-this-in-production-xyz789'
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = False  # Mettre à True en production avec HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Upload
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'Courbes')
    EXPORT_FOLDER = os.path.join(BASE_DIR, 'Export')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max
    ALLOWED_EXTENSIONS = {'csv'}
    
    # Login
    LOGIN_VIEW = 'login'
    LOGIN_MESSAGE = 'Veuillez vous connecter pour accéder à cette page.'
    LOGIN_MESSAGE_CATEGORY = 'error'
    
    # CAPTCHA
    CAPTCHA_MIN_NUMBER = 1
    CAPTCHA_MAX_NUMBER = 20
    
    @staticmethod
    def init_app(app):
        """Initialisation de l'application"""
        # Créer les dossiers nécessaires
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.EXPORT_FOLDER, exist_ok=True)


class DevelopmentConfig(Config):
    """Configuration pour le développement"""
    DEBUG = True
    TESTING = False
    
    # En développement, afficher les erreurs SQL
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    """Configuration pour la production"""
    DEBUG = False
    TESTING = False
    
    # Sécurité renforcée en production
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY must be set in production environment")
    
    SESSION_COOKIE_SECURE = True  # Nécessite HTTPS
    WTF_CSRF_ENABLED = True
    
    # Désactiver l'écho SQL en production
    SQLALCHEMY_ECHO = False
    
    # Base de données de production (peut être PostgreSQL, MySQL, etc.)
    # SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')


class TestingConfig(Config):
    """Configuration pour les tests"""
    TESTING = True
    DEBUG = True
    
    # Base de données en mémoire pour les tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Désactiver CSRF pour les tests
    WTF_CSRF_ENABLED = False
    
    # Login sans redirection pour les tests
    LOGIN_DISABLED = True


# Dictionnaire de configurations
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Obtenir la configuration selon l'environnement"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])