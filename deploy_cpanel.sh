#!/bin/bash
# deploy_cpanel.sh - Script de déploiement pour cPanel

echo "================================================"
echo "   Déploiement RepartKey sur cPanel"
echo "================================================"

# Variables
APP_DIR="/home/votre_utilisateur/public_html/RepartElec"
BACKUP_DIR="/home/votre_utilisateur/backups/repartkey"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Fonction pour afficher les messages
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Vérifier que nous sommes dans le bon répertoire
if [ ! -f "app_auth.py" ]; then
    log_error "Ce script doit être exécuté depuis le répertoire de l'application"
    exit 1
fi

# Créer le répertoire de sauvegarde
log_info "Création du répertoire de sauvegarde..."
mkdir -p "$BACKUP_DIR"

# Sauvegarde de l'ancienne version
if [ -d "$APP_DIR" ]; then
    log_info "Sauvegarde de l'ancienne version..."
    tar -czf "$BACKUP_DIR/backup_$TIMESTAMP.tar.gz" -C "$APP_DIR" . 2>/dev/null
    log_info "Sauvegarde créée: backup_$TIMESTAMP.tar.gz"
fi

# Créer le répertoire de l'application s'il n'existe pas
log_info "Création du répertoire de l'application..."
mkdir -p "$APP_DIR"

# Copier les fichiers Python
log_info "Copie des fichiers Python..."
cp app_auth.py "$APP_DIR/app.py"  # Renommer pour cPanel
cp models.py "$APP_DIR/"
cp forms.py "$APP_DIR/"
cp config.py "$APP_DIR/"
cp Consumer.py "$APP_DIR/"
cp Producer.py "$APP_DIR/"
cp Repartition.py "$APP_DIR/"
cp Graph.py "$APP_DIR/"

# Copier les templates
log_info "Copie des templates..."
mkdir -p "$APP_DIR/templates"
cp templates/*.html "$APP_DIR/templates/"

# Créer les répertoires nécessaires
log_info "Création des répertoires de données..."
mkdir -p "$APP_DIR/Courbes"
mkdir -p "$APP_DIR/Export"
mkdir -p "$APP_DIR/static"

# Définir les permissions
log_info "Configuration des permissions..."
chmod 755 "$APP_DIR"
chmod 755 "$APP_DIR/app.py"
chmod 755 "$APP_DIR"/*.py
chmod -R 755 "$APP_DIR/templates"
chmod -R 777 "$APP_DIR/Courbes"
chmod -R 777 "$APP_DIR/Export"
chmod 777 "$APP_DIR"  # Pour la base de données SQLite

# Créer le fichier .htaccess pour cPanel
log_info "Création du fichier .htaccess..."
cat > "$APP_DIR/.htaccess" << 'EOF'
RewriteEngine On
RewriteBase /RepartElec/

# Rediriger toutes les requêtes vers app.py
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^(.*)$ app.py/$1 [L]

# Configuration Python
AddHandler cgi-script .py
Options +ExecCGI

# Sécurité
<FilesMatch "\.(db|sqlite|sqlite3)$">
    Order deny,allow
    Deny from all
</FilesMatch>

# Cache pour les fichiers statiques
<IfModule mod_expires.c>
    ExpiresActive On
    ExpiresByType image/jpg "access plus 1 month"
    ExpiresByType image/jpeg "access plus 1 month"
    ExpiresByType image/gif "access plus 1 month"
    ExpiresByType image/png "access plus 1 month"
    ExpiresByType text/css "access plus 1 week"
    ExpiresByType application/javascript "access plus 1 week"
</IfModule>
EOF

# Créer le fichier passenger_wsgi.py pour certains hébergeurs
log_info "Création du fichier passenger_wsgi.py..."
cat > "$APP_DIR/passenger_wsgi.py" << 'EOF'
#!/usr/bin/env python
import sys
import os

# Ajouter le répertoire de l'application au path
sys.path.insert(0, os.path.dirname(__file__))

# Importer l'application
from app import app as application

# Configuration pour la production
os.environ['FLASK_ENV'] = 'production'

if __name__ == "__main__":
    application.run()
EOF

chmod 755 "$APP_DIR/passenger_wsgi.py"

# Créer un fichier de configuration production
log_info "Création du fichier .env de production..."
cat > "$APP_DIR/.env" << EOF
FLASK_ENV=production
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
SESSION_COOKIE_SECURE=False
DATABASE_URL=sqlite:///repartkey.db
EOF

chmod 600 "$APP_DIR/.env"

# Créer le fichier requirements.txt local
log_info "Copie du fichier requirements.txt..."
cp requirements.txt "$APP_DIR/"

# Instructions pour l'installation des dépendances
log_info "Instructions pour installer les dépendances Python..."
cat << EOF

================================================
INSTALLATION DES DÉPENDANCES
================================================

Connectez-vous à votre cPanel et utilisez le Terminal ou SSH pour exécuter:

cd $APP_DIR
pip install --user -r requirements.txt

Ou utilisez l'interface "Python App" de cPanel si disponible.

================================================
MIGRATION DES DONNÉES (si nécessaire)
================================================

Si vous avez des données existantes à migrer:

1. Copiez l'ancienne base de données:
   cp /chemin/vers/textblocks.db $APP_DIR/

2. Exécutez le script de migration:
   cd $APP_DIR
   python migrate_data.py

================================================
VÉRIFICATION
================================================

1. Accédez à: https://votre-domaine.com/RepartElec/
2. Créez un compte utilisateur
3. Testez la création d'un projet

================================================
EN CAS DE PROBLÈME
================================================

1. Vérifiez les logs d'erreur dans cPanel
2. Vérifiez les permissions des fichiers
3. Restaurez depuis la sauvegarde si nécessaire:
   tar -xzf $BACKUP_DIR/backup_$TIMESTAMP.tar.gz -C $APP_DIR

EOF

log_info "Déploiement terminé!"