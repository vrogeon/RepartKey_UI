#!/usr/bin/env python3
# migrate_to_rgpd.py - Script de migration automatique pour le système RGPD

import os
import sys
import shutil
from datetime import datetime

# Ajouter le répertoire au path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def print_header(text):
    """Afficher un en-tête formaté"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def print_step(number, text):
    """Afficher une étape"""
    print(f"\n[Étape {number}] {text}")

def print_success(text):
    """Afficher un succès"""
    print(f"  ✅ {text}")

def print_error(text):
    """Afficher une erreur"""
    print(f"  ❌ {text}")

def print_warning(text):
    """Afficher un avertissement"""
    print(f"  ⚠️  {text}")

def print_info(text):
    """Afficher une info"""
    print(f"  ℹ️  {text}")

class RGPDMigration:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
    def check_requirements(self):
        """Vérifier les prérequis"""
        print_step(1, "Vérification des prérequis")
        
        # Vérifier que app_auth.py existe
        if not os.path.exists('app_auth.py'):
            self.errors.append("app_auth.py non trouvé - êtes-vous dans le bon répertoire ?")
            print_error("app_auth.py non trouvé")
            return False
        print_success("app_auth.py trouvé")
        
        # Vérifier que le dossier templates existe
        if not os.path.exists('templates'):
            print_warning("Dossier templates non trouvé - création...")
            os.makedirs('templates', exist_ok=True)
            print_success("Dossier templates créé")
        else:
            print_success("Dossier templates trouvé")
        
        # Vérifier que cookies_consent.py existe
        if not os.path.exists('cookies_consent.py'):
            self.errors.append("cookies_consent.py non trouvé - veuillez le créer d'abord")
            print_error("cookies_consent.py non trouvé")
            return False
        print_success("cookies_consent.py trouvé")
        
        return True
    
    def backup_files(self):
        """Créer des sauvegardes"""
        print_step(2, "Création des sauvegardes")
        
        backup_dir = f"backup_rgpd_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            os.makedirs(backup_dir, exist_ok=True)
            
            # Sauvegarder app_auth.py
            if os.path.exists('app_auth.py'):
                shutil.copy2('app_auth.py', os.path.join(backup_dir, 'app_auth.py'))
                print_success(f"app_auth.py sauvegardé dans {backup_dir}")
            
            # Sauvegarder la base de données
            if os.path.exists('repartkey.db'):
                shutil.copy2('repartkey.db', os.path.join(backup_dir, 'repartkey.db'))
                print_success(f"Base de données sauvegardée dans {backup_dir}")
            
            return backup_dir
        except Exception as e:
            self.errors.append(f"Erreur lors de la sauvegarde : {e}")
            print_error(f"Erreur : {e}")
            return None
    
    def create_database_table(self):
        """Créer la table cookie_consents"""
        print_step(3, "Création de la table cookie_consents")
        
        try:
            from app_auth import app, db
            from cookies_consent import CookieConsent
            
            with app.app_context():
                # Créer la table
                db.create_all()
                
                # Vérifier qu'elle existe
                inspector = db.inspect(db.engine)
                tables = inspector.get_table_names()
                
                if 'cookie_consents' in tables:
                    print_success("Table cookie_consents créée/vérifiée")
                    return True
                else:
                    print_error("Table cookie_consents non créée")
                    return False
                    
        except ImportError as e:
            print_error(f"Erreur d'import : {e}")
            print_info("Assurez-vous que cookies_consent.py est présent")
            return False
        except Exception as e:
            print_error(f"Erreur : {e}")
            return False
    
    def update_app_auth(self):
        """Modifier app_auth.py pour intégrer le système RGPD"""
        print_step(4, "Modification de app_auth.py")
        
        try:
            with open('app_auth.py', 'r', encoding='utf-8') as f:
                content = f.read()
            
            modifications = []
            
            # Vérifier si déjà modifié
            if 'cookies_consent' in content:
                print_info("app_auth.py semble déjà modifié pour RGPD")
                return True
            
            # Trouver où ajouter l'import
            import_line = "from cookies_consent import cookies_bp, CookieManager, CookieConsent"
            if import_line not in content:
                # Ajouter après les imports de models
                if "from models import" in content:
                    content = content.replace(
                        "from models import",
                        f"from models import"
                    )
                    # Ajouter l'import après
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if "from models import" in line:
                            lines.insert(i+1, import_line)
                            break
                    content = '\n'.join(lines)
                    modifications.append("Import RGPD ajouté")
            
            # Ajouter l'enregistrement du blueprint
            blueprint_line = "app.register_blueprint(cookies_bp)"
            if blueprint_line not in content:
                # Trouver où l'ajouter (après login_manager.init_app)
                if "login_manager.init_app(app)" in content:
                    content = content.replace(
                        "login_manager.init_app(app)",
                        f"login_manager.init_app(app)\n\n# Enregistrer le blueprint RGPD\n{blueprint_line}"
                    )
                    modifications.append("Blueprint RGPD enregistré")
            
            if modifications:
                # Sauvegarder les modifications
                with open('app_auth.py', 'w', encoding='utf-8') as f:
                    f.write(content)
                
                for mod in modifications:
                    print_success(mod)
                print_info("app_auth.py modifié - vérifiez manuellement si nécessaire")
            else:
                print_info("Aucune modification nécessaire dans app_auth.py")
            
            return True
            
        except Exception as e:
            print_error(f"Erreur lors de la modification : {e}")
            self.warnings.append("app_auth.py doit être modifié manuellement")
            return False
    
    def check_templates(self):
        """Vérifier la présence des templates"""
        print_step(5, "Vérification des templates")
        
        templates = [
            'cookie_banner.html',
            'cookie_policy.html', 
            'cookie_preferences.html'
        ]
        
        all_present = True
        for template in templates:
            path = os.path.join('templates', template)
            if os.path.exists(path):
                print_success(f"{template} présent")
            else:
                print_error(f"{template} manquant")
                all_present = False
                self.errors.append(f"Template {template} manquant dans templates/")
        
        return all_present
    
    def update_base_template(self):
        """Ajouter la bannière dans base.html ou index.html"""
        print_step(6, "Intégration de la bannière dans les templates")
        
        # Chercher base.html ou index.html
        base_template = None
        if os.path.exists('templates/base.html'):
            base_template = 'templates/base.html'
        elif os.path.exists('templates/index.html'):
            base_template = 'templates/index.html'
        
        if not base_template:
            print_warning("Ni base.html ni index.html trouvé")
            print_info("Ajoutez manuellement {% include 'cookie_banner.html' %} avant </body>")
            self.warnings.append("Intégration manuelle de la bannière requise")
            return False
        
        try:
            with open(base_template, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Vérifier si déjà présent
            if 'cookie_banner.html' in content:
                print_info(f"Bannière déjà intégrée dans {base_template}")
                return True
            
            # Ajouter avant </body>
            if '</body>' in content:
                banner_include = "\n<!-- Bannière RGPD -->\n{% include 'cookie_banner.html' %}\n\n</body>"
                content = content.replace('</body>', banner_include)
                
                with open(base_template, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print_success(f"Bannière intégrée dans {base_template}")
                return True
            else:
                print_warning(f"</body> non trouvé dans {base_template}")
                self.warnings.append("Intégration manuelle de la bannière requise")
                return False
                
        except Exception as e:
            print_error(f"Erreur : {e}")
            self.warnings.append("Intégration manuelle de la bannière requise")
            return False
    
    def create_maintenance_scripts(self):
        """Créer les scripts de maintenance"""
        print_step(7, "Création des scripts de maintenance")
        
        # Script de nettoyage
        cleanup_script = '''#!/usr/bin/env python3
# cleanup_cookies.py - Nettoyage des consentements expirés

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app_auth import app
from cookies_consent import cleanup_old_consents

with app.app_context():
    deleted = cleanup_old_consents()
    print(f"✅ {deleted} consentements expirés supprimés")
'''
        
        try:
            with open('cleanup_cookies.py', 'w', encoding='utf-8') as f:
                f.write(cleanup_script)
            
            # Rendre exécutable sur Unix
            if os.name != 'nt':
                os.chmod('cleanup_cookies.py', 0o755)
            
            print_success("Script cleanup_cookies.py créé")
            print_info("Ajoutez au cron : 0 2 * * 0 /usr/bin/python3 cleanup_cookies.py")
            return True
            
        except Exception as e:
            print_warning(f"Impossible de créer le script : {e}")
            return False
    
    def show_summary(self):
        """Afficher le résumé"""
        print_header("RÉSUMÉ DE LA MIGRATION")
        
        if not self.errors:
            print("\n🎉 Migration réussie !\n")
            print("✅ Table cookie_consents créée")
            print("✅ Système RGPD intégré")
            print("\n📋 Prochaines étapes :")
            print("  1. Redémarrez l'application")
            print("  2. Testez en navigation privée")
            print("  3. Vérifiez que la bannière apparaît")
            print("  4. Testez les préférences de cookies")
            
            if self.warnings:
                print("\n⚠️  Points d'attention :")
                for warning in self.warnings:
                    print(f"  - {warning}")
        else:
            print("\n❌ Migration incomplète\n")
            print("Erreurs rencontrées :")
            for error in self.errors:
                print(f"  - {error}")
            
            print("\nCorrigez ces erreurs et relancez la migration")
    
    def run(self):
        """Exécuter la migration complète"""
        print_header("MIGRATION RGPD POUR REPARTKEY")
        print("\nCe script va :")
        print("  • Créer la table cookie_consents")
        print("  • Modifier app_auth.py")
        print("  • Vérifier les templates")
        print("  • Créer les scripts de maintenance")
        
        response = input("\n▶️  Continuer ? (o/N) : ").strip().lower()
        if response not in ['o', 'oui', 'y', 'yes']:
            print("\n❌ Migration annulée")
            return False
        
        # Étapes de migration
        if not self.check_requirements():
            self.show_summary()
            return False
        
        backup_dir = self.backup_files()
        if backup_dir:
            print_info(f"Sauvegardes dans : {backup_dir}")
        
        self.create_database_table()
        self.update_app_auth()
        self.check_templates()
        self.update_base_template()
        self.create_maintenance_scripts()
        
        self.show_summary()
        
        return len(self.errors) == 0


def main():
    """Point d'entrée principal"""
    migration = RGPDMigration()
    success = migration.run()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrompue")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Erreur inattendue : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)