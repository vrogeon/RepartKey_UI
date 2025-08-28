# cookies_consent.py - Système de gestion du consentement RGPD

from flask import Blueprint, render_template, request, jsonify, make_response
from datetime import datetime, timedelta
from models import db
import json

# Blueprint pour la gestion des cookies
cookies_bp = Blueprint('cookies', __name__)

# Modèle pour stocker les consentements (optionnel, on peut aussi utiliser uniquement les cookies)
class CookieConsent(db.Model):
    __tablename__ = 'cookie_consents'
    
    id = db.Column(db.Integer, primary_key=True)
    user_ip = db.Column(db.String(45), nullable=False)  # Support IPv6
    user_agent_hash = db.Column(db.String(64), nullable=False)
    essential_cookies = db.Column(db.Boolean, default=True)  # Toujours True
    performance_cookies = db.Column(db.Boolean, default=False)
    marketing_cookies = db.Column(db.Boolean, default=False)
    consent_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    consent_version = db.Column(db.String(10), default='1.0')

    def __repr__(self):
        return f'<CookieConsent {self.user_ip}>'

    def to_dict(self):
        return {
            'essential_cookies': self.essential_cookies,
            'performance_cookies': self.performance_cookies,
            'marketing_cookies': self.marketing_cookies,
            'consent_date': self.consent_date.isoformat(),
            'consent_version': self.consent_version
        }

# Configuration des types de cookies
COOKIE_CATEGORIES = {
    'essential': {
        'name': 'Cookies essentiels',
        'description': 'Ces cookies sont strictement nécessaires au fonctionnement du site. Ils ne peuvent pas être désactivés.',
        'required': True,
        'cookies': [
            {
                'name': 'session',
                'purpose': 'Gestion de la session utilisateur et authentification',
                'duration': 'Session'
            },
            {
                'name': 'demo_session_id',
                'purpose': 'Fonctionnement du mode démonstration',
                'duration': '1 heure'
            },
            {
                'name': 'csrf_token',
                'purpose': 'Protection contre les attaques CSRF',
                'duration': 'Session'
            }
        ]
    },
    'performance': {
        'name': 'Cookies de performance',
        'description': 'Ces cookies nous aident à améliorer les performances du site en collectant des informations anonymes sur son utilisation.',
        'required': False,
        'cookies': [
            {
                'name': 'user_preferences',
                'purpose': 'Sauvegarde des préférences d\'interface (largeur sidebar, etc.)',
                'duration': '1 an'
            }
        ]
    },
    'marketing': {
        'name': 'Cookies marketing',
        'description': 'Ces cookies peuvent être définis par nos partenaires publicitaires pour créer un profil de vos intérêts.',
        'required': False,
        'cookies': [
            # Actuellement aucun cookie marketing dans l'application
        ]
    }
}

@cookies_bp.route('/cookies/consent', methods=['POST'])
def save_consent():
    """Sauvegarder le consentement de l'utilisateur"""
    try:
        data = request.get_json()
        
        essential = data.get('essential', True)
        performance = data.get('performance', False)
        marketing = data.get('marketing', False)
        
        # Créer la réponse
        response_data = {
            'success': True,
            'message': 'Préférences sauvegardées avec succès'
        }
        
        response = make_response(jsonify(response_data))
        
        # Sauvegarder les préférences dans un cookie (dur 1 an)
        consent_data = {
            'essential': essential,
            'performance': performance,
            'marketing': marketing,
            'version': '1.0',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        response.set_cookie(
            'cookie_consent',
            json.dumps(consent_data),
            max_age=365*24*60*60,  # 1 an
            secure=request.is_secure,
            httponly=False,  # JavaScript doit pouvoir lire ce cookie
            samesite='Lax'
        )
        
        # Optionnel : sauvegarder aussi en base de données
        try:
            import hashlib
            user_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', ''))
            user_agent_hash = hashlib.sha256(request.headers.get('User-Agent', '').encode()).hexdigest()
            
            # Chercher un consentement existant
            existing_consent = CookieConsent.query.filter_by(
                user_ip=user_ip,
                user_agent_hash=user_agent_hash
            ).first()
            
            if existing_consent:
                existing_consent.essential_cookies = essential
                existing_consent.performance_cookies = performance
                existing_consent.marketing_cookies = marketing
                existing_consent.last_updated = datetime.utcnow()
            else:
                new_consent = CookieConsent(
                    user_ip=user_ip,
                    user_agent_hash=user_agent_hash,
                    essential_cookies=essential,
                    performance_cookies=performance,
                    marketing_cookies=marketing
                )
                db.session.add(new_consent)
            
            db.session.commit()
        except Exception as e:
            print(f"Erreur sauvegarde consentement DB: {e}")
        
        return response
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erreur lors de la sauvegarde: {str(e)}'
        }), 500

@cookies_bp.route('/cookies/preferences')
def cookie_preferences():
    """Page de gestion des préférences de cookies"""
    return render_template('cookie_preferences.html', 
                         cookie_categories=COOKIE_CATEGORIES)

@cookies_bp.route('/cookies/policy')
def cookie_policy():
    """Page de politique des cookies"""
    return render_template('cookie_policy.html', 
                         cookie_categories=COOKIE_CATEGORIES)

def get_user_cookie_consent():
    """Récupérer le consentement de l'utilisateur depuis les cookies"""
    consent_cookie = request.cookies.get('cookie_consent')
    
    if not consent_cookie:
        return None
    
    try:
        consent_data = json.loads(consent_cookie)
        return consent_data
    except:
        return None

def has_consent_for_category(category):
    """Vérifier si l'utilisateur a donné son consentement pour une catégorie"""
    if category == 'essential':
        return True  # Les cookies essentiels ne nécessitent pas de consentement
    
    consent = get_user_cookie_consent()
    if not consent:
        return False
    
    return consent.get(category, False)

# Fonction à utiliser dans les templates
def inject_cookie_consent():
    """Injecter les informations de consentement dans tous les templates"""
    return {
        'cookie_consent': get_user_cookie_consent(),
        'has_consent_for_category': has_consent_for_category
    }