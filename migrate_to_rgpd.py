# migrate_to_rgpd.py - Script de migration pour intégrer le système RGPD

import os
import sys
from datetime import datetime
import hashlib

# Ajouter le répertoire de l'application au path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app_auth import app, db
from models import User
from cookies_consent import CookieConsent

class RGPDMigrator:
    """Gestionnaire de migration pour le système RGPD"""
    
    def __init__(self):
        self.migration_log = []
        self.errors = []
    
    def log(self, message, level='INFO'):
        """Enregistrer un message de log"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {level}: {message}"
        self.migration_log.append(log_entry)
        print(log_entry)
    
    def error(self, message, exception=None):
        """Enregistrer une erreur"""
        error_msg = f"ERREUR: {message}"
        if exception:
            error_msg += f" - {str(exception)}"
        self.errors.append(error_msg)
        self.log(error_msg, 'ERROR')
    
    def create_cookie_consent_table(self):
        """Créer la table de consentement des cookies"""
        try:
            with app.app_context():
                # Vérifier si la table existe déjà
                inspector = db.inspect(db.engine)
                if 'cookie_consents' in inspector.get_table_names():
                    self.log("Table 'cookie_consents' existe déjà")
                    return True
                
                # Créer la table
                db.create_all()
                self.log("Table 'cookie_consents' créée avec succès")
                return True
                
        except Exception as e:
            self.error("Erreur lors de la création de la table cookie_consents", e)
            return False
    
    def migrate_existing_users(self):
        """Migrer les utilisateurs existants avec consentement par défaut"""
        try:
            with app.app_context():
                users = User.query.all()
                migrated_count = 0
                
                for user in users:
                    try:
                        # Créer un hash basique pour l'utilisateur
                        user_hash = hashlib.sha256(f"{user.username}_{user.email}".encode()).hexdigest()
                        
                        # Vérifier si un consentement existe déjà
                        existing = CookieConsent.query.filter_by(
                            user_agent_hash=user_hash
                        ).first()
                        
                        if existing:
                            self.log(f"Consentement existant pour {user.username}")
                            continue
                        
                        # Créer un consentement par défaut (cookies essentiels uniquement)
                        consent = CookieConsent(
                            user_ip='127.0.0.1',  # IP générique pour la migration
                            user_agent_hash=user_hash,
                            essential_cookies=True,
                            performance_cookies=False,  # Par défaut désactivé
                            marketing_cookies=False,
                            consent_version='1.0'
                        )
                        
                        db.session.add(consent)
                        migrated_count += 1
                        
                    except Exception as e:
                        self.error(f"Erreur migration utilisateur {user.username}", e)
                        continue
                
                db.session.commit()
                self.log(f"Migration de {migrated_count} utilisateurs terminée")
                return True
                
        except Exception as e:
            self.error("Erreur lors de la migration des utilisateurs", e)
            return False
    
    def create_privacy_pages(self):
        """Créer les fichiers de pages de confidentialité si ils n'existent pas"""
        try:
            templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
            
            required_templates = [
                'cookie_banner.html',
                'cookie_policy.html',
                'cookie_preferences.html'
            ]
            
            missing_templates = []
            
            for template in required_templates:
                template_path = os.path.join(templates_dir, template)
                if not os.path.exists(template_path):
                    missing_templates.append(template)
            
            if missing_templates:
                self.log(f"Templates manquants: {', '.join(missing_templates)}")
                self.log("Veuillez créer ces templates avec le contenu fourni dans la documentation")
                return False
            
            self.log("Tous les templates RGPD sont présents")
            return True
            
        except Exception as e:
            self.error("Erreur lors de la vérification des templates", e)
            return False
    
    def update_app_config(self):
        """Vérifier et suggérer les modifications de configuration"""
        config_suggestions = []
        
        # Vérifier la clé secrète
        if app.config.get('SECRET_KEY') == 'your-secret-key-change-this-in-production-2024':
            config_suggestions.append("⚠️  IMPORTANT: Changez la SECRET_KEY en production")
        
        # Vérifier la configuration des cookies
        if not app.config.get('SESSION_COOKIE_SECURE'):
            config_suggestions.append("💡 Recommandé: Activer SESSION_COOKIE_SECURE en production HTTPS")
        
        if not app.config.get('SESSION_COOKIE_HTTPONLY'):
            config_suggestions.append("💡 Recommandé: Activer SESSION_COOKIE_HTTPONLY pour la sécurité")
        
        if config_suggestions:
            self.log("Suggestions de configuration:")
            for suggestion in config_suggestions:
                self.log(f"  {suggestion}")
        else:
            self.log("Configuration des cookies correcte")
        
        return True
    
    def verify_routes(self):
        """Vérifier que les routes RGPD sont disponibles"""
        try:
            with app.app_context():
                # Vérifier les routes importantes
                from flask import url_for
                
                required_routes = [
                    ('cookies.save_consent', 'POST /cookies/consent'),
                    ('cookies.cookie_policy', 'GET /cookies/policy'),
                    ('cookies.cookie_preferences', 'GET /cookies/preferences')
                ]
                
                for route_name, description in required_routes:
                    try:
                        url_for(route_name)
                        self.log(f"✓ Route {description} disponible")
                    except Exception:
                        self.error(f"✗ Route {description} manquante")
                        return False
                
                return True
                
        except Exception as e:
            self.error("Erreur lors de la vérification des routes", e)
            return False
    
    def create_cookie_cleanup_job(self):
        """Créer un script de nettoyage automatique des anciens consentements"""
        cleanup_script = '''#!/usr/bin/env python3
# cleanup_old_consents.py - Script de nettoyage automatique RGPD
# À exécuter périodiquement (ex: cron mensuel)

import os
import sys
from datetime import datetime, timedelta

# Ajouter le répertoire de l'application
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app_auth import app, db
from cookies_consent import CookieConsent

def cleanup_old_consents():
    """Supprimer les consentements de plus de 12 mois"""
    with app.app_context():
        # Date limite (12 mois)
        cutoff_date = datetime.utcnow() - timedelta(days=365)
        
        # Trouver les anciens consentements
        old_consents = CookieConsent.query.filter(
            CookieConsent.last_updated < cutoff_date
        ).all()
        
        print(f"Trouvé {len(old_consents)} consentements à supprimer")
        
        # Supprimer
        for consent in old_consents:
            db.session.delete(consent)
        
        db.session.commit()
        print(f"Nettoyage terminé: {len(old_consents)} consentements supprimés")

if __name__ == '__main__':
    cleanup_old_consents()
'''
        
        try:
            script_path = os.path.join(os.path.dirname(__file__), 'cleanup_old_consents.py')
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(cleanup_script)
            
            # Rendre le script exécutable
            os.chmod(script_path, 0o755)
            
            self.log(f"Script de nettoyage créé: {script_path}")
            self.log("💡 Ajoutez ce script au cron pour un nettoyage mensuel:")
            self.log("   0 2 1 * * /path/to/cleanup_old_consents.py")
            
            return True
            
        except Exception as e:
            self.error("Erreur lors de la création du script de nettoyage", e)
            return False
    
    def create_backup_config(self):
        """Créer une configuration de sauvegarde des données RGPD"""
        backup_config = '''# backup_rgpd.sh - Script de sauvegarde RGPD
#!/bin/bash

# Configuration
BACKUP_DIR="/path/to/backups/rgpd"
DB_FILE="/path/to/repartkey.db"
DATE=$(date +%Y%m%d_%H%M%S)

# Créer le répertoire de sauvegarde
mkdir -p "$BACKUP_DIR"

# Sauvegarder la base de données
cp "$DB_FILE" "$BACKUP_DIR/repartkey_rgpd_$DATE.db"

# Sauvegarder uniquement les tables RGPD
sqlite3 "$DB_FILE" ".dump cookie_consents" > "$BACKUP_DIR/cookie_consents_$DATE.sql"

# Nettoyer les anciennes sauvegardes (> 30 jours)
find "$BACKUP_DIR" -name "*.db" -mtime +30 -delete
find "$BACKUP_DIR" -name "*.sql" -mtime +30 -delete

echo "Sauvegarde RGPD terminée: $DATE"
'''
        
        try:
            script_path = os.path.join(os.path.dirname(__file__), 'backup_rgpd.sh')
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(backup_config)
            
            os.chmod(script_path, 0o755)
            
            self.log(f"Script de sauvegarde créé: {script_path}")
            self.log("💡 Configurez ce script pour des sauvegardes régulières")
            
            return True
            
        except Exception as e:
            self.error("Erreur lors de la création du script de sauvegarde", e)
            return False
    
    def run_migration(self):
        """Exécuter la migration complète"""
        self.log("🚀 DÉBUT DE LA MIGRATION RGPD")
        self.log("=" * 50)
        
        steps = [
            ("Création de la table cookie_consents", self.create_cookie_consent_table),
            ("Migration des utilisateurs existants", self.migrate_existing_users),
            ("Vérification des templates", self.create_privacy_pages),
            ("Vérification de la configuration", self.update_app_config),
            ("Vérification des routes", self.verify_routes),
            ("Création du script de nettoyage", self.create_cookie_cleanup_job),
            ("Création du script de sauvegarde", self.create_backup_config),
        ]
        
        success_count = 0
        total_steps = len(steps)
        
        for step_name, step_function in steps:
            self.log(f"📋 {step_name}...")
            if step_function():
                success_count += 1
                self.log(f"✅ {step_name} - SUCCÈS")
            else:
                self.log(f"❌ {step_name} - ÉCHEC")
            self.log("-" * 30)
        
        # Résumé
        self.log("=" * 50)
        self.log("📊 RÉSUMÉ DE LA MIGRATION")
        self.log(f"✅ Étapes réussies: {success_count}/{total_steps}")
        self.log(f"❌ Erreurs: {len(self.errors)}")
        
        if self.errors:
            self.log("\n🔍 ERREURS DÉTAILLÉES:")
            for error in self.errors:
                self.log(f"  {error}")
        
        if success_count == total_steps:
            self.log("\n🎉 MIGRATION RGPD TERMINÉE AVEC SUCCÈS!")
            self.log("\n📋 PROCHAINES ÉTAPES:")
            self.log("1. Vérifiez que tous les templates sont correctement créés")
            self.log("2. Testez le banner de consentement")
            self.log("3. Vérifiez les pages de politique des cookies")
            self.log("4. Configurez les tâches cron pour le nettoyage automatique")
            self.log("5. Mettez à jour la SECRET_KEY en production")
            self.log("6. Activez HTTPS et les cookies sécurisés en production")
        else:
            self.log("\n⚠️  MIGRATION INCOMPLÈTE - Veuillez corriger les erreurs")
        
        return success_count == total_steps
    
    def generate_report(self):
        """Générer un rapport de migration"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f"rgpd_migration_report_{timestamp}.txt"
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("RAPPORT DE MIGRATION RGPD\n")
                f.write("=" * 50 + "\n")
                f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Erreurs: {len(self.errors)}\n\n")
                
                f.write("LOG COMPLET:\n")
                f.write("-" * 20 + "\n")
                for log_entry in self.migration_log:
                    f.write(log_entry + "\n")
                
                if self.errors:
                    f.write("\nERREURS:\n")
                    f.write("-" * 20 + "\n")
                    for error in self.errors:
                        f.write(error + "\n")
            
            self.log(f"📄 Rapport sauvegardé: {report_file}")
            return report_file
            
        except Exception as e:
            self.error("Erreur lors de la génération du rapport", e)
            return None


def main():
    """Fonction principale de migration"""
    print("🍪 MIGRATION RGPD POUR REPARTKEY")
    print("=" * 40)
    print()
    
    # Vérification préliminaire
    if not os.path.exists('app_auth.py'):
        print("❌ Erreur: Ce script doit être exécuté depuis le répertoire de RepartKey")
        print("   (app_auth.py non trouvé)")
        return False
    
    # Demander confirmation
    print("Cette migration va:")
    print("• Créer la table 'cookie_consents' dans la base de données")
    print("• Migrer les utilisateurs existants avec consentement par défaut") 
    print("• Vérifier la présence des templates RGPD")
    print("• Créer des scripts de maintenance automatique")
    print()
    
    response = input("Continuer la migration ? (o/N): ").strip().lower()
    if response not in ['o', 'oui', 'y', 'yes']:
        print("Migration annulée par l'utilisateur")
        return False
    
    # Créer une sauvegarde de la base de données
    print("📦 Création d'une sauvegarde de sécurité...")
    try:
        import shutil
        db_file = 'repartkey.db'
        if os.path.exists(db_file):
            backup_name = f"repartkey_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2(db_file, backup_name)
            print(f"✅ Sauvegarde créée: {backup_name}")
    except Exception as e:
        print(f"⚠️  Impossible de créer la sauvegarde: {e}")
        response = input("Continuer sans sauvegarde ? (o/N): ").strip().lower()
        if response not in ['o', 'oui', 'y', 'yes']:
            print("Migration annulée")
            return False
    
    # Lancer la migration
    migrator = RGPDMigrator()
    success = migrator.run_migration()
    
    # Générer le rapport
    migrator.generate_report()
    
    return success


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrompue par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)