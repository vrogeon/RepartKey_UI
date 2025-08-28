# cookies_consent.py - Module de gestion RGPD des cookies

from flask import Blueprint, request, make_response, jsonify, render_template, current_app
from flask_login import current_user
from datetime import datetime, timedelta
import json
import hashlib
from models import db

# Blueprint pour les routes liées aux cookies
cookies_bp = Blueprint('cookies', __name__, url_prefix='/cookies')


class CookieConsent(db.Model):
    """Modèle pour stocker les consentements des utilisateurs"""
    __tablename__ = 'cookie_consents'
    
    id = db.Column(db.Integer, primary_key=True)
    user_ip = db.Column(db.String(45))  # IPv4 ou IPv6
    user_agent_hash = db.Column(db.String(64))  # Hash du user agent pour l'unicité
    
    # Consentements par catégorie
    essential_cookies = db.Column(db.Boolean, default=True, nullable=False)  # Toujours True (obligatoires)
    performance_cookies = db.Column(db.Boolean, default=False)
    marketing_cookies = db.Column(db.Boolean, default=False)
    
    # Métadonnées
    consent_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    consent_version = db.Column(db.String(10), default='1.0')  # Version de la politique
    
    # Lien optionnel avec un utilisateur connecté
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    def __repr__(self):
        return f'<CookieConsent {self.id}>'
    
    def to_dict(self):
        """Convertir en dictionnaire pour l'API"""
        return {
            'essential': self.essential_cookies,
            'performance': self.performance_cookies,
            'marketing': self.marketing_cookies,
            'consent_date': self.consent_date.isoformat() if self.consent_date else None,
            'version': self.consent_version
        }


class CookieManager:
    """Gestionnaire principal des cookies RGPD"""
    
    # Durée de validité du consentement (13 mois selon RGPD)
    CONSENT_DURATION_DAYS = 13 * 30  # ~13 mois
    
    # Types de cookies
    COOKIE_TYPES = {
        'essential': {
            'name': 'Cookies essentiels',
            'description': 'Ces cookies sont nécessaires au fonctionnement du site. Ils permettent l\'authentification, la sécurité et la navigation basique.',
            'cookies': ['session', 'csrf_token', 'cookie_consent'],
            'required': True
        },
        'performance': {
            'name': 'Cookies de performance',
            'description': 'Ces cookies nous aident à comprendre comment les visiteurs utilisent notre site, nous permettant d\'améliorer les performances et l\'expérience utilisateur.',
            'cookies': ['_ga', '_gid', 'analytics_id'],
            'required': False
        },
        'marketing': {
            'name': 'Cookies marketing',
            'description': 'Ces cookies sont utilisés pour personnaliser le contenu et les publicités, et pour analyser notre trafic.',
            'cookies': ['_fbp', 'ads_session'],
            'required': False
        }
    }
    
    @staticmethod
    def get_user_identifier(request):
        """Obtenir un identifiant unique pour l'utilisateur"""
        user_agent = request.headers.get('User-Agent', '')
        user_ip = CookieManager.get_real_ip(request)
        
        # Créer un hash unique basé sur l'IP et le User-Agent
        identifier = f"{user_ip}_{user_agent}"
        return hashlib.sha256(identifier.encode()).hexdigest()
    
    @staticmethod
    def get_real_ip(request):
        """Obtenir l'IP réelle de l'utilisateur (gestion des proxys)"""
        if request.environ.get('HTTP_X_FORWARDED_FOR'):
            return request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
        elif request.environ.get('HTTP_X_REAL_IP'):
            return request.environ['HTTP_X_REAL_IP']
        else:
            return request.environ.get('REMOTE_ADDR', '')
    
    @staticmethod
    def has_valid_consent(request):
        """Vérifier si l'utilisateur a un consentement valide"""
        # Vérifier le cookie de consentement
        consent_cookie = request.cookies.get('cookie_consent')
        if not consent_cookie:
            return False
        
        try:
            consent_data = json.loads(consent_cookie)
            consent_date = datetime.fromisoformat(consent_data.get('date', ''))
            
            # Vérifier si le consentement n'est pas expiré
            if datetime.utcnow() - consent_date > timedelta(days=CookieManager.CONSENT_DURATION_DAYS):
                return False
            
            return True
        except (json.JSONDecodeError, ValueError):
            return False
    
    @staticmethod
    def get_consent_preferences(request):
        """Obtenir les préférences de consentement actuelles"""
        consent_cookie = request.cookies.get('cookie_consent')
        if not consent_cookie:
            return None
        
        try:
            return json.loads(consent_cookie)
        except json.JSONDecodeError:
            return None
    
    @staticmethod
    def save_consent(user_ip, user_agent_hash, essential, performance, marketing, user_id=None):
        """Sauvegarder le consentement en base de données"""
        # Chercher un consentement existant
        consent = CookieConsent.query.filter_by(
            user_agent_hash=user_agent_hash,
            user_ip=user_ip
        ).first()
        
        if consent:
            # Mettre à jour le consentement existant
            consent.essential_cookies = essential
            consent.performance_cookies = performance
            consent.marketing_cookies = marketing
            consent.last_updated = datetime.utcnow()
            if user_id:
                consent.user_id = user_id
        else:
            # Créer un nouveau consentement
            consent = CookieConsent(
                user_ip=user_ip,
                user_agent_hash=user_agent_hash,
                essential_cookies=essential,
                performance_cookies=performance,
                marketing_cookies=marketing,
                user_id=user_id
            )
            db.session.add(consent)
        
        db.session.commit()
        return consent
    
    @staticmethod
    def create_consent_cookie(consent_data):
        """Créer le cookie de consentement"""
        cookie_data = {
            'essential': consent_data.get('essential', True),
            'performance': consent_data.get('performance', False),
            'marketing': consent_data.get('marketing', False),
            'date': datetime.utcnow().isoformat(),
            'version': '1.0'
        }
        
        return json.dumps(cookie_data)
    
    @staticmethod
    def clean_non_consented_cookies(response, consent_preferences):
        """Supprimer les cookies non consentis"""
        if not consent_preferences:
            return response
        
        # Si pas de consentement pour les cookies de performance
        if not consent_preferences.get('performance', False):
            for cookie_name in CookieManager.COOKIE_TYPES['performance']['cookies']:
                response.set_cookie(cookie_name, '', expires=0)
        
        # Si pas de consentement pour les cookies marketing
        if not consent_preferences.get('marketing', False):
            for cookie_name in CookieManager.COOKIE_TYPES['marketing']['cookies']:
                response.set_cookie(cookie_name, '', expires=0)
        
        return response


# Routes du blueprint
@cookies_bp.route('/consent', methods=['POST'])
def save_consent():
    """Route pour sauvegarder le consentement des cookies"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Données manquantes'}), 400
    
    # Obtenir les préférences
    essential = True  # Toujours true
    performance = data.get('performance', False)
    marketing = data.get('marketing', False)
    
    # Obtenir les identifiants
    user_ip = CookieManager.get_real_ip(request)
    user_agent_hash = CookieManager.get_user_identifier(request)
    user_id = current_user.id if current_user.is_authenticated else None
    
    # Sauvegarder en base
    consent = CookieManager.save_consent(
        user_ip=user_ip,
        user_agent_hash=user_agent_hash,
        essential=essential,
        performance=performance,
        marketing=marketing,
        user_id=user_id
    )
    
    # Créer la réponse avec le cookie de consentement
    response = make_response(jsonify({
        'success': True,
        'message': 'Préférences enregistrées'
    }))
    
    # Définir le cookie de consentement
    cookie_value = CookieManager.create_consent_cookie({
        'essential': essential,
        'performance': performance,
        'marketing': marketing
    })
    
    response.set_cookie(
        'cookie_consent',
        cookie_value,
        max_age=CookieManager.CONSENT_DURATION_DAYS * 24 * 60 * 60,  # En secondes
        secure=current_app.config.get('SESSION_COOKIE_SECURE', False),
        httponly=True,
        samesite='Lax'
    )
    
    # Nettoyer les cookies non consentis
    if not performance:
        for cookie in CookieManager.COOKIE_TYPES['performance']['cookies']:
            response.set_cookie(cookie, '', expires=0)
    
    if not marketing:
        for cookie in CookieManager.COOKIE_TYPES['marketing']['cookies']:
            response.set_cookie(cookie, '', expires=0)
    
    return response


@cookies_bp.route('/preferences', methods=['GET'])
def get_preferences():
    """Route pour obtenir les préférences actuelles"""
    preferences = CookieManager.get_consent_preferences(request)
    
    if preferences:
        return jsonify(preferences)
    
    # Préférences par défaut
    return jsonify({
        'essential': True,
        'performance': False,
        'marketing': False,
        'date': None,
        'version': '1.0'
    })


@cookies_bp.route('/policy', methods=['GET'])
def cookie_policy():
    """Page de politique des cookies"""
    return render_template('cookie_policy.html', 
                         cookie_types=CookieManager.COOKIE_TYPES,
                         consent_duration=CookieManager.CONSENT_DURATION_DAYS)


@cookies_bp.route('/settings', methods=['GET'])
def cookie_preferences():
    """Page de gestion des préférences"""
    current_preferences = CookieManager.get_consent_preferences(request)
    return render_template('cookie_preferences.html',
                         cookie_types=CookieManager.COOKIE_TYPES,
                         current_preferences=current_preferences)


# Middleware pour vérifier le consentement
def check_cookie_consent():
    """Middleware pour vérifier le consentement avant chaque requête"""
    # Exclure certaines routes
    excluded_paths = ['/cookies/', '/static/', '/login', '/register']
    
    if any(request.path.startswith(path) for path in excluded_paths):
        return
    
    # Vérifier si l'utilisateur a donné son consentement
    if not CookieManager.has_valid_consent(request):
        # Le consentement sera demandé via JavaScript dans le template
        pass


# Fonction pour nettoyer les anciens consentements
def cleanup_old_consents():
    """Nettoyer les consentements expirés (à exécuter périodiquement)"""
    cutoff_date = datetime.utcnow() - timedelta(days=CookieManager.CONSENT_DURATION_DAYS)
    
    old_consents = CookieConsent.query.filter(
        CookieConsent.consent_date < cutoff_date
    ).all()
    
    for consent in old_consents:
        db.session.delete(consent)
    
    db.session.commit()
    
    return len(old_consents)