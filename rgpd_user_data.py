# rgpd_user_data.py - Gestion des données utilisateur selon RGPD

from flask import Blueprint, request, jsonify, render_template, make_response
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from models import db, User, Project, ConsumerBlock, ProducerBlock, TextBlock
from cookies_consent import CookieConsent
import json
import hashlib
import zipfile
import tempfile
import os

# Blueprint pour la gestion des données utilisateur RGPD
rgpd_user_bp = Blueprint('rgpd_user', __name__, url_prefix='/rgpd')

@rgpd_user_bp.route('/my-data')
@login_required
def my_data_page():
    """Page de gestion des données personnelles de l'utilisateur"""
    return render_template('rgpd_my_data.html')

@rgpd_user_bp.route('/api/data-summary')
@login_required
def data_summary():
    """Résumé des données personnelles de l'utilisateur"""
    try:
        user = current_user
        
        # Compter les différents types de données
        projects_count = user.projects.count()
        consumers_count = db.session.query(ConsumerBlock).join(Project).filter(
            Project.user_id == user.id
        ).count()
        producers_count = db.session.query(ProducerBlock).join(Project).filter(
            Project.user_id == user.id
        ).count()
        text_blocks_count = db.session.query(TextBlock).join(Project).filter(
            Project.user_id == user.id
        ).count()
        
        # Chercher les consentements de cookies
        user_hash = hashlib.sha256(f"{user.username}_{user.email}".encode()).hexdigest()
        cookie_consent = CookieConsent.query.filter_by(
            user_agent_hash=user_hash
        ).first()
        
        # Calculer l'ancienneté du compte
        account_age = (datetime.utcnow() - user.date_created).days
        
        # Dernière activité (dernière modification de projet)
        last_project = user.projects.order_by(Project.last_modified.desc()).first()
        last_activity = last_project.last_modified if last_project else user.date_created
        
        return jsonify({
            'user_info': {
                'username': user.username,
                'email': user.email,
                'account_created': user.date_created.isoformat(),
                'account_age_days': account_age,
                'last_activity': last_activity.isoformat()
            },
            'data_summary': {
                'projects': projects_count,
                'consumers': consumers_count,
                'producers': producers_count,
                'text_blocks': text_blocks_count,
                'has_cookie_consent': cookie_consent is not None
            },
            'cookie_consent': {
                'has_consent': cookie_consent is not None,
                'essential_cookies': cookie_consent.essential_cookies if cookie_consent else None,
                'performance_cookies': cookie_consent.performance_cookies if cookie_consent else None,
                'marketing_cookies': cookie_consent.marketing_cookies if cookie_consent else None,
                'consent_date': cookie_consent.consent_date.isoformat() if cookie_consent else None,
                'last_updated': cookie_consent.last_updated.isoformat() if cookie_consent else None
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@rgpd_user_bp.route('/api/export-data')
@login_required
def export_user_data():
    """Exporter toutes les données personnelles de l'utilisateur (droit à la portabilité)"""
    try:
        user = current_user
        
        # Préparer les données d'export
        export_data = {
            'export_info': {
                'requested_by': user.username,
                'export_date': datetime.utcnow().isoformat(),
                'export_type': 'complete_user_data',
                'rgpd_basis': 'Article 20 - Droit à la portabilité des données'
            },
            'user_profile': {
                'username': user.username,
                'email': user.email,
                'date_created': user.date_created.isoformat(),
                'account_id': user.id
            },
            'projects': [],
            'cookie_consents': [],
            'usage_statistics': {}
        }
        
        # Exporter les projets et leurs données
        for project in user.projects:
            project_data = {
                'id': project.id,
                'name': project.name,
                'description': project.description,
                'created_date': project.date_created.isoformat(),
                'last_modified': project.last_modified.isoformat(),
                'is_active': project.is_active,
                'consumers': [],
                'producers': [],
                'text_blocks': []
            }
            
            # Exporter les consommateurs du projet
            for consumer in project.consumer_blocks:
                consumer_data = {
                    'id': consumer.id,
                    'name': consumer.cons_name,
                    'prm': consumer.prm,
                    'tarif_type': consumer.tarif_type,
                    'tarif_normal': consumer.tarif_normal,
                    'tarif_hc': consumer.tarif_hc,
                    'tarif_hp': consumer.tarif_hp,
                    'created_date': consumer.date_created.isoformat(),
                    'has_file': consumer.has_file(),
                    'file_name': consumer.get_file_name()
                }
                project_data['consumers'].append(consumer_data)
            
            # Exporter les producteurs du projet
            for producer in project.producer_blocks:
                producer_data = {
                    'id': producer.id,
                    'name': producer.prod_name,
                    'created_date': producer.date_created.isoformat(),
                    'has_file': producer.has_file(),
                    'file_name': producer.get_file_name()
                }
                project_data['producers'].append(producer_data)
            
            # Exporter les blocs de texte du projet
            for text_block in project.text_blocks:
                text_data = {
                    'id': text_block.id,
                    'title': text_block.title,
                    'content': text_block.content,
                    'created_date': text_block.date_created.isoformat()
                }
                project_data['text_blocks'].append(text_data)
            
            export_data['projects'].append(project_data)
        
        # Exporter les consentements de cookies
        user_hash = hashlib.sha256(f"{user.username}_{user.email}".encode()).hexdigest()
        cookie_consents = CookieConsent.query.filter_by(
            user_agent_hash=user_hash
        ).all()
        
        for consent in cookie_consents:
            consent_data = {
                'essential_cookies': consent.essential_cookies,
                'performance_cookies': consent.performance_cookies,
                'marketing_cookies': consent.marketing_cookies,
                'consent_date': consent.consent_date.isoformat(),
                'last_updated': consent.last_updated.isoformat(),
                'consent_version': consent.consent_version
            }
            export_data['cookie_consents'].append(consent_data)
        
        # Statistiques d'utilisation (anonymisées)
        export_data['usage_statistics'] = {
            'total_projects': len(export_data['projects']),
            'total_consumers': sum(len(p['consumers']) for p in export_data['projects']),
            'total_producers': sum(len(p['producers']) for p in export_data['projects']),
            'most_recent_project': max(p['last_modified'] for p in export_data['projects']) if export_data['projects'] else None,
            'account_age_days': (datetime.utcnow() - user.date_created).days
        }
        
        # Créer la réponse avec les données JSON
        response = make_response(jsonify(export_data))
        response.headers['Content-Disposition'] = f'attachment; filename=mes_donnees_repartkey_{datetime.now().strftime("%Y%m%d")}.json'
        response.headers['Content-Type'] = 'application/json'
        
        return response
        
    except Exception as e:
        return jsonify({'error': f'Erreur lors de l\'export: {str(e)}'}), 500

@rgpd_user_bp.route('/api/delete-data', methods=['POST'])
@login_required
def request_data_deletion():
    """Demander la suppression des données personnelles (droit à l'effacement)"""
    try:
        data = request.get_json()
        deletion_type = data.get('type', 'partial')  # 'partial' ou 'complete'
        confirmation_text = data.get('confirmation', '')
        
        user = current_user
        
        # Vérifier la confirmation
        expected_confirmation = f"SUPPRIMER {user.username}"
        if confirmation_text != expected_confirmation:
            return jsonify({
                'error': 'Confirmation incorrecte',
                'expected': expected_confirmation
            }), 400
        
        deletion_report = {
            'deletion_date': datetime.utcnow().isoformat(),
            'user_id': user.id,
            'username': user.username,
            'deletion_type': deletion_type,
            'deleted_items': []
        }
        
        if deletion_type == 'complete':
            # Suppression complète du compte et de toutes les données
            
            # 1. Supprimer les consentements de cookies
            user_hash = hashlib.sha256(f"{user.username}_{user.email}".encode()).hexdigest()
            cookie_consents = CookieConsent.query.filter_by(user_agent_hash=user_hash).all()
            for consent in cookie_consents:
                db.session.delete(consent)
            deletion_report['deleted_items'].append(f"{len(cookie_consents)} consentements de cookies")
            
            # 2. Supprimer tous les projets (cascade automatique pour les données associées)
            projects = user.projects.all()
            project_count = len(projects)
            for project in projects:
                # Les ConsumerBlocks, ProducerBlocks et TextBlocks seront supprimés automatiquement
                # grâce aux relations cascade dans les modèles
                db.session.delete(project)
            deletion_report['deleted_items'].append(f"{project_count} projets avec toutes leurs données")
            
            # 3. Supprimer l'utilisateur lui-même
            username = user.username
            db.session.delete(user)
            deletion_report['deleted_items'].append("Compte utilisateur")
            
            db.session.commit()
            
            # Déconnecter l'utilisateur
            from flask_login import logout_user
            logout_user()
            
            return jsonify({
                'success': True,
                'message': f'Compte {username} supprimé définitivement',
                'deletion_report': deletion_report,
                'redirect': '/login'
            })
            
        elif deletion_type == 'partial':
            # Suppression partielle - garder le compte mais supprimer les données de projets
            
            projects = user.projects.all()
            project_count = len(projects)
            
            total_consumers = 0
            total_producers = 0
            total_text_blocks = 0
            
            for project in projects:
                total_consumers += project.consumer_blocks.count()
                total_producers += project.producer_blocks.count()
                total_text_blocks += project.text_blocks.count()
                db.session.delete(project)
            
            deletion_report['deleted_items'].extend([
                f"{project_count} projets",
                f"{total_consumers} consommateurs",
                f"{total_producers} producteurs",
                f"{total_text_blocks} blocs de texte"
            ])
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Données de projets supprimées avec succès',
                'deletion_report': deletion_report,
                'account_preserved': True
            })
            
        else:
            return jsonify({'error': 'Type de suppression non reconnu'}), 400
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erreur lors de la suppression: {str(e)}'}), 500

@rgpd_user_bp.route('/api/data-rectification', methods=['POST'])
@login_required
def rectify_user_data():
    """Rectifier les données personnelles (droit de rectification)"""
    try:
        data = request.get_json()
        user = current_user
        
        updated_fields = []
        
        # Permettre la modification de l'email uniquement
        if 'email' in data:
            new_email = data['email'].strip()
            if new_email != user.email:
                # Vérifier que l'email n'est pas déjà utilisé
                existing_user = User.query.filter_by(email=new_email).first()
                if existing_user and existing_user.id != user.id:
                    return jsonify({'error': 'Cet email est déjà utilisé par un autre compte'}), 400
                
                old_email = user.email
                user.email = new_email
                updated_fields.append(f"Email: {old_email} → {new_email}")
        
        # Note: Le nom d'utilisateur ne peut généralement pas être modifié
        # pour des raisons de cohérence des données
        
        if updated_fields:
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Données mises à jour avec succès',
                'updated_fields': updated_fields,
                'updated_at': datetime.utcnow().isoformat()
            })
        else:
            return jsonify({
                'success': True,
                'message': 'Aucune modification apportée'
            })
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erreur lors de la rectification: {str(e)}'}), 500

@rgpd_user_bp.route('/api/data-restriction', methods=['POST'])
@login_required
def restrict_data_processing():
    """Limiter le traitement des données (droit à la limitation)"""
    try:
        data = request.get_json()
        user = current_user
        restriction_type = data.get('type', 'temporary')
        
        # Pour l'exemple, on peut désactiver temporairement les projets
        if restriction_type == 'temporary':
            # Désactiver tous les projets de l'utilisateur
            projects = user.projects.all()
            for project in projects:
                project.is_active = False
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'{len(projects)} projets désactivés temporairement',
                'restriction_applied': 'temporary_deactivation',
                'can_reactivate': True
            })
            
        elif restriction_type == 'reactivate':
            # Réactiver tous les projets
            projects = user.projects.all()
            for project in projects:
                project.is_active = True
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'{len(projects)} projets réactivés',
                'restriction_removed': True
            })
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erreur lors de la restriction: {str(e)}'}), 500

@rgpd_user_bp.route('/api/cookie-consent-history')
@login_required
def cookie_consent_history():
    """Historique des consentements de cookies de l'utilisateur"""
    try:
        user = current_user
        user_hash = hashlib.sha256(f"{user.username}_{user.email}".encode()).hexdigest()
        
        consents = CookieConsent.query.filter_by(
            user_agent_hash=user_hash
        ).order_by(CookieConsent.last_updated.desc()).all()
        
        consent_history = []
        for consent in consents:
            consent_data = {
                'id': consent.id,
                'essential_cookies': consent.essential_cookies,
                'performance_cookies': consent.performance_cookies,
                'marketing_cookies': consent.marketing_cookies,
                'consent_date': consent.consent_date.isoformat(),
                'last_updated': consent.last_updated.isoformat(),
                'version': consent.consent_version,
                'is_current': consent == consents[0] if consents else False,
                'days_since_update': (datetime.utcnow() - consent.last_updated).days
            }
            consent_history.append(consent_data)
        
        return jsonify({
            'consent_history': consent_history,
            'total_consents': len(consent_history),
            'current_consent': consent_history[0] if consent_history else None
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Classe pour générer des rapports personnels RGPD
class PersonalDataReportGenerator:
    """Générateur de rapports personnels pour les utilisateurs"""
    
    def __init__(self, user):
        self.user = user
        self.generated_at = datetime.utcnow()
    
    def generate_privacy_report(self):
        """Générer un rapport de confidentialité personnel"""
        try:
            # Analyser les données personnelles
            projects = self.user.projects.all()
            
            # Calculer les métriques de vie privée
            privacy_score = self._calculate_privacy_score()
            
            report = {
                'report_info': {
                    'user': self.user.username,
                    'generated_at': self.generated_at.isoformat(),
                    'report_type': 'personal_privacy_report'
                },
                'privacy_score': privacy_score,
                'data_summary': {
                    'account_age_days': (self.generated_at - self.user.date_created).days,
                    'total_projects': len(projects),
                    'active_projects': sum(1 for p in projects if p.is_active),
                    'last_activity': max(p.last_modified for p in projects).isoformat() if projects else None
                },
                'cookie_preferences': self._get_cookie_preferences(),
                'recommendations': self._generate_privacy_recommendations(privacy_score)
            }
            
            return report
            
        except Exception as e:
            return {'error': str(e)}
    
    def _calculate_privacy_score(self):
        """Calculer un score de confidentialité pour l'utilisateur"""
        score = 100
        
        # Vérifier les consentements de cookies
        user_hash = hashlib.sha256(f"{self.user.username}_{self.user.email}".encode()).hexdigest()
        cookie_consent = CookieConsent.query.filter_by(user_agent_hash=user_hash).first()
        
        if not cookie_consent:
            score -= 20  # Pas de consentement enregistré
        else:
            # Bonus pour avoir configuré ses préférences
            if not cookie_consent.performance_cookies and not cookie_consent.marketing_cookies:
                score += 10  # Utilisateur soucieux de sa vie privée
        
        # Vérifier l'âge du compte
        account_age = (self.generated_at - self.user.date_created).days
        if account_age < 30:
            score -= 5  # Nouveau compte, moins de données historiques
        
        return max(0, min(100, score))
    
    def _get_cookie_preferences(self):
        """Récupérer les préférences de cookies actuelles"""
        user_hash = hashlib.sha256(f"{self.user.username}_{self.user.email}".encode()).hexdigest()
        cookie_consent = CookieConsent.query.filter_by(user_agent_hash=user_hash).first()
        
        if cookie_consent:
            return {
                'essential_cookies': cookie_consent.essential_cookies,
                'performance_cookies': cookie_consent.performance_cookies,
                'marketing_cookies': cookie_consent.marketing_cookies,
                'last_updated': cookie_consent.last_updated.isoformat(),
                'version': cookie_consent.consent_version
            }
        else:
            return {
                'configured': False,
                'message': 'Aucune préférence de cookies configurée'
            }
    
    def _generate_privacy_recommendations(self, score):
        """Générer des recommandations pour améliorer la confidentialité"""
        recommendations = []
        
        if score < 70:
            recommendations.append("Configurez vos préférences de cookies pour un meilleur contrôle")
        
        if score < 80:
            recommendations.append("Vérifiez régulièrement vos paramètres de confidentialité")
        
        user_hash = hashlib.sha256(f"{self.user.username}_{self.user.email}".encode()).hexdigest()
        cookie_consent = CookieConsent.query.filter_by(user_agent_hash=user_hash).first()
        
        if cookie_consent and (self.generated_at - cookie_consent.last_updated).days > 180:
            recommendations.append("Mettez à jour vos préférences de cookies (dernière mise à jour il y a plus de 6 mois)")
        
        if not recommendations:
            recommendations.append("Excellente gestion de votre vie privée ! Continuez ainsi.")
        
        return recommendations

@rgpd_user_bp.route('/api/privacy-report')
@login_required
def generate_privacy_report():
    """Générer un rapport de confidentialité personnel"""
    try:
        generator = PersonalDataReportGenerator(current_user)
        report = generator.generate_privacy_report()
        
        if 'error' in report:
            return jsonify({'error': report['error']}), 500
        
        return jsonify(report)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500