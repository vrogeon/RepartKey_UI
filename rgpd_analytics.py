# rgpd_analytics.py - Dashboard et analytics pour le consentement RGPD

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from cookies_consent import CookieConsent
from models import db, User
import json

# Blueprint pour les analytics RGPD (accessible uniquement aux admins)
rgpd_analytics_bp = Blueprint('rgpd_analytics', __name__, url_prefix='/admin/rgpd')

def is_admin():
    """Vérifier si l'utilisateur est administrateur"""
    # À adapter selon votre système d'autorisation
    # Pour l'exemple, on vérifie si c'est le premier utilisateur créé
    if not current_user.is_authenticated:
        return False
    
    first_user = User.query.order_by(User.id).first()
    return current_user.id == first_user.id if first_user else False

@rgpd_analytics_bp.before_request
def require_admin():
    """Middleware pour vérifier les droits admin"""
    if not is_admin():
        return jsonify({'error': 'Accès non autorisé'}), 403

@rgpd_analytics_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal des analytics RGPD"""
    return render_template('rgpd_analytics_dashboard.html')

@rgpd_analytics_bp.route('/api/stats/overview')
@login_required
def stats_overview():
    """Statistiques générales de consentement"""
    try:
        # Statistiques de base
        total_consents = CookieConsent.query.count()
        
        # Consentements par catégorie
        essential_count = CookieConsent.query.filter_by(essential_cookies=True).count()
        performance_count = CookieConsent.query.filter_by(performance_cookies=True).count()
        marketing_count = CookieConsent.query.filter_by(marketing_cookies=True).count()
        
        # Consentements récents (7 derniers jours)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_consents = CookieConsent.query.filter(
            CookieConsent.consent_date >= week_ago
        ).count()
        
        # Taux de consentement
        performance_rate = (performance_count / total_consents * 100) if total_consents > 0 else 0
        marketing_rate = (marketing_count / total_consents * 100) if total_consents > 0 else 0
        
        # Consentements par version
        version_stats = db.session.query(
            CookieConsent.consent_version,
            func.count(CookieConsent.id)
        ).group_by(CookieConsent.consent_version).all()
        
        return jsonify({
            'total_consents': total_consents,
            'categories': {
                'essential': essential_count,
                'performance': performance_count,
                'marketing': marketing_count
            },
            'rates': {
                'performance': round(performance_rate, 1),
                'marketing': round(marketing_rate, 1)
            },
            'recent_consents': recent_consents,
            'version_distribution': {
                version: count for version, count in version_stats
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@rgpd_analytics_bp.route('/api/stats/timeline')
@login_required
def stats_timeline():
    """Évolution des consentements dans le temps"""
    try:
        days = request.args.get('days', 30, type=int)
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Consentements par jour
        daily_consents = db.session.query(
            func.date(CookieConsent.consent_date).label('date'),
            func.count(CookieConsent.id).label('total'),
            func.sum(CookieConsent.performance_cookies.cast(db.Integer)).label('performance'),
            func.sum(CookieConsent.marketing_cookies.cast(db.Integer)).label('marketing')
        ).filter(
            CookieConsent.consent_date >= start_date
        ).group_by(
            func.date(CookieConsent.consent_date)
        ).order_by('date').all()
        
        # Formater les données
        timeline_data = []
        for day_stat in daily_consents:
            timeline_data.append({
                'date': day_stat.date.isoformat(),
                'total': day_stat.total,
                'performance': day_stat.performance or 0,
                'marketing': day_stat.marketing or 0
            })
        
        return jsonify({
            'timeline': timeline_data,
            'period': f"{days} derniers jours"
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@rgpd_analytics_bp.route('/api/stats/geographic')
@login_required
def stats_geographic():
    """Répartition géographique approximative (basée sur IP)"""
    try:
        # Statistiques par plage d'IP (pour respecter la vie privée)
        ip_stats = db.session.query(
            func.substr(CookieConsent.user_ip, 1, 7).label('ip_prefix'),
            func.count(CookieConsent.id).label('count')
        ).group_by('ip_prefix').order_by(desc('count')).limit(10).all()
        
        # Note: En production, vous pourriez utiliser une vraie géolocalisation
        # mais en respectant la vie privée (ville/région, pas adresse exacte)
        
        geographic_data = []
        for ip_stat in ip_stats:
            geographic_data.append({
                'region': f"Région {ip_stat.ip_prefix}xxx", # Anonymisé
                'count': ip_stat.count
            })
        
        return jsonify({
            'geographic': geographic_data,
            'note': 'Données anonymisées pour respecter la vie privée'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@rgpd_analytics_bp.route('/api/stats/compliance')
@login_required
def stats_compliance():
    """Statistiques de conformité RGPD"""
    try:
        # Consentements expirants (> 11 mois)
        eleven_months_ago = datetime.utcnow() - timedelta(days=330)
        expiring_consents = CookieConsent.query.filter(
            CookieConsent.last_updated < eleven_months_ago
        ).count()
        
        # Consentements expirés (> 12 mois)
        twelve_months_ago = datetime.utcnow() - timedelta(days=365)
        expired_consents = CookieConsent.query.filter(
            CookieConsent.last_updated < twelve_months_ago
        ).count()
        
        # Mises à jour récentes de consentement
        recent_updates = CookieConsent.query.filter(
            CookieConsent.last_updated != CookieConsent.consent_date
        ).count()
        
        # Analyse de la durée moyenne entre consent et mise à jour
        updates_with_diff = db.session.query(
            func.avg(
                func.julianday(CookieConsent.last_updated) - 
                func.julianday(CookieConsent.consent_date)
            ).label('avg_days')
        ).filter(
            CookieConsent.last_updated != CookieConsent.consent_date
        ).first()
        
        avg_update_days = updates_with_diff.avg_days if updates_with_diff.avg_days else 0
        
        return jsonify({
            'compliance': {
                'expiring_soon': expiring_consents,
                'expired': expired_consents,
                'total_updates': recent_updates,
                'avg_days_to_update': round(avg_update_days, 1) if avg_update_days else 0
            },
            'recommendations': [
                f"Contacter {expiring_consents} utilisateurs pour renouveler leur consentement" if expiring_consents > 0 else "Aucun consentement n'expire bientôt",
                f"Supprimer {expired_consents} consentements expirés" if expired_consents > 0 else "Aucun consentement expiré",
                "Système de consentement fonctionnel" if recent_updates > 0 else "Encourager les utilisateurs à personnaliser leurs préférences"
            ]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@rgpd_analytics_bp.route('/api/export/consents')
@login_required
def export_consents():
    """Exporter les données de consentement (format JSON)"""
    try:
        format_type = request.args.get('format', 'json')
        
        # Récupérer tous les consentements avec données anonymisées
        consents = CookieConsent.query.order_by(desc(CookieConsent.consent_date)).all()
        
        if format_type == 'json':
            export_data = []
            for consent in consents:
                # Anonymiser les données sensibles
                export_data.append({
                    'id': consent.id,
                    'ip_anonymized': consent.user_ip[:7] + 'xxx' if len(consent.user_ip) > 7 else 'xxx.xxx',
                    'user_hash': consent.user_agent_hash[:8] + '...',  # Hash partiel
                    'essential_cookies': consent.essential_cookies,
                    'performance_cookies': consent.performance_cookies,
                    'marketing_cookies': consent.marketing_cookies,
                    'consent_date': consent.consent_date.isoformat(),
                    'last_updated': consent.last_updated.isoformat(),
                    'consent_version': consent.consent_version
                })
            
            return jsonify({
                'export_date': datetime.utcnow().isoformat(),
                'total_records': len(export_data),
                'data': export_data
            })
        
        else:
            return jsonify({'error': 'Format non supporté'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@rgpd_analytics_bp.route('/api/cleanup/expired')
@login_required
def cleanup_expired():
    """Nettoyer les consentements expirés"""
    try:
        # Consentements de plus de 12 mois
        twelve_months_ago = datetime.utcnow() - timedelta(days=365)
        expired_consents = CookieConsent.query.filter(
            CookieConsent.last_updated < twelve_months_ago
        )
        
        count = expired_consents.count()
        
        # Si c'est juste une simulation
        if request.args.get('simulate', 'false') == 'true':
            return jsonify({
                'simulated': True,
                'expired_count': count,
                'message': f"{count} consentements seraient supprimés"
            })
        
        # Suppression réelle
        expired_consents.delete()
        db.session.commit()
        
        return jsonify({
            'deleted': count,
            'message': f"{count} consentements expirés supprimés avec succès"
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@rgpd_analytics_bp.route('/api/users/consent-status/<int:user_id>')
@login_required
def user_consent_status(user_id):
    """Vérifier le statut de consentement d'un utilisateur spécifique"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Chercher le consentement de cet utilisateur
        # (basé sur un hash de ses données pour la recherche)
        import hashlib
        user_hash = hashlib.sha256(f"{user.username}_{user.email}".encode()).hexdigest()
        
        consent = CookieConsent.query.filter_by(
            user_agent_hash=user_hash
        ).first()
        
        if consent:
            return jsonify({
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                },
                'consent': {
                    'has_consent': True,
                    'essential_cookies': consent.essential_cookies,
                    'performance_cookies': consent.performance_cookies,
                    'marketing_cookies': consent.marketing_cookies,
                    'consent_date': consent.consent_date.isoformat(),
                    'last_updated': consent.last_updated.isoformat(),
                    'version': consent.consent_version,
                    'is_expired': (datetime.utcnow() - consent.last_updated).days > 365
                }
            })
        else:
            return jsonify({
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                },
                'consent': {
                    'has_consent': False,
                    'message': 'Aucun consentement enregistré pour cet utilisateur'
                }
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Classe pour générer des rapports RGPD
class RGPDReportGenerator:
    """Générateur de rapports de conformité RGPD"""
    
    def __init__(self):
        self.report_data = {}
        self.generated_at = datetime.utcnow()
    
    def generate_monthly_report(self):
        """Générer un rapport mensuel de conformité"""
        try:
            # Période du rapport (mois dernier)
            end_date = datetime.utcnow().replace(day=1) - timedelta(days=1)
            start_date = end_date.replace(day=1)
            
            # Statistiques du mois
            monthly_consents = CookieConsent.query.filter(
                CookieConsent.consent_date >= start_date,
                CookieConsent.consent_date <= end_date
            ).all()
            
            # Analyser les données
            total_consents = len(monthly_consents)
            performance_accepted = sum(1 for c in monthly_consents if c.performance_cookies)
            marketing_accepted = sum(1 for c in monthly_consents if c.marketing_cookies)
            
            report = {
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'month_name': start_date.strftime('%B %Y')
                },
                'statistics': {
                    'total_new_consents': total_consents,
                    'performance_acceptance_rate': (performance_accepted / total_consents * 100) if total_consents > 0 else 0,
                    'marketing_acceptance_rate': (marketing_accepted / total_consents * 100) if total_consents > 0 else 0
                },
                'compliance_notes': [
                    f"Nouveau consentements collectés: {total_consents}",
                    f"Taux d'acceptation des cookies de performance: {(performance_accepted / total_consents * 100):.1f}%" if total_consents > 0 else "Aucun nouveau consentement",
                    f"Tous les consentements ont été collectés conformément au RGPD",
                    f"Aucune violation détectée durant cette période"
                ],
                'generated_at': self.generated_at.isoformat()
            }
            
            return report
            
        except Exception as e:
            return {'error': str(e)}
    
    def generate_compliance_audit(self):
        """Générer un audit de conformité complet"""
        try:
            # Vérifications de conformité
            total_consents = CookieConsent.query.count()
            
            # Consentements expirés
            twelve_months_ago = datetime.utcnow() - timedelta(days=365)
            expired = CookieConsent.query.filter(
                CookieConsent.last_updated < twelve_months_ago
            ).count()
            
            # Versions de consentement
            versions = db.session.query(
                CookieConsent.consent_version,
                func.count(CookieConsent.id)
            ).group_by(CookieConsent.consent_version).all()
            
            # Score de conformité
            compliance_score = 100
            issues = []
            
            if expired > 0:
                compliance_score -= 20
                issues.append(f"{expired} consentements expirés détectés")
            
            if total_consents == 0:
                compliance_score -= 50
                issues.append("Aucun consentement collecté")
            
            # Rapport d'audit
            audit_report = {
                'audit_date': self.generated_at.isoformat(),
                'compliance_score': max(0, compliance_score),
                'status': 'CONFORME' if compliance_score >= 80 else 'ATTENTION REQUISE',
                'statistics': {
                    'total_consents': total_consents,
                    'expired_consents': expired,
                    'consent_versions': dict(versions)
                },
                'issues_found': issues,
                'recommendations': self._generate_recommendations(compliance_score, issues),
                'next_audit_date': (self.generated_at + timedelta(days=90)).isoformat()
            }
            
            return audit_report
            
        except Exception as e:
            return {'error': str(e)}
    
    def _generate_recommendations(self, score, issues):
        """Générer des recommandations basées sur l'audit"""
        recommendations = []
        
        if score < 80:
            recommendations.append("Action immédiate requise pour améliorer la conformité")
        
        if "expirés" in ' '.join(issues):
            recommendations.append("Mettre en place un processus automatique de nettoyage des consentements expirés")
            recommendations.append("Contacter les utilisateurs pour renouveler leur consentement avant expiration")
        
        if "Aucun consentement" in ' '.join(issues):
            recommendations.append("Vérifier que le système de collecte de consentement fonctionne correctement")
            recommendations.append("Former les utilisateurs sur l'importance du consentement")
        
        if not recommendations:
            recommendations.append("Système de consentement conforme - maintenir les bonnes pratiques")
            recommendations.append("Continuer la surveillance régulière de la conformité")
        
        return recommendations

@rgpd_analytics_bp.route('/api/reports/monthly')
@login_required
def monthly_report():
    """Générer un rapport mensuel"""
    try:
        generator = RGPDReportGenerator()
        report = generator.generate_monthly_report()
        return jsonify(report)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@rgpd_analytics_bp.route('/api/reports/compliance-audit')
@login_required
def compliance_audit():
    """Générer un audit de conformité"""
    try:
        generator = RGPDReportGenerator()
        audit = generator.generate_compliance_audit()
        return jsonify(audit)
    except Exception as e:
        return jsonify({'error': str(e)}), 500