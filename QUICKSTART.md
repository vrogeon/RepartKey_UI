# 🚀 Guide de démarrage rapide - RepartElec avec authentification

## Installation en 5 minutes

### 1️⃣ Installation des dépendances

```bash
pip install -r requirements.txt
```

### 2️⃣ Configuration minimale

Créez un fichier `.env` :
```bash
FLASK_ENV=development
SECRET_KEY=dev-key-123456789
```

### 3️⃣ Initialisation de la base de données

```python
python
>>> from app_auth import app, db
>>> with app.app_context():
...     db.create_all()
>>> exit()
```

### 4️⃣ Lancement de l'application

```bash
python app_auth.py
```

### 5️⃣ Accès à l'application

Ouvrez votre navigateur : http://localhost:5000

---

## 🔐 Première utilisation

### Créer votre compte

1. Cliquez sur **"S'inscrire"**
2. Remplissez le formulaire :
   - Nom d'utilisateur (min. 3 caractères)
   - Email valide
   - Mot de passe (min. 6 caractères)
   - Répondez au CAPTCHA mathématique
3. Cliquez sur **"S'inscrire"**

### Se connecter

1. Entrez vos identifiants
2. Répondez au CAPTCHA
3. Cliquez sur **"Se connecter"**

### Créer votre premier projet

1. Une fois connecté, cliquez sur **"➕ Nouveau Projet"**
2. Donnez un nom à votre projet
3. Ajoutez une description (optionnel)
4. Cliquez sur **"Créer le projet"**

---

## 📊 Utilisation de base

### Dans un projet

1. **Ajouter un producteur** :
   - Cliquez sur "Ajouter" dans la colonne Producteur
   - Donnez un nom
   - Uploadez le fichier CSV de production

2. **Ajouter un consommateur** :
   - Cliquez sur "Ajouter" dans la ligne Consommateur
   - Donnez un nom
   - Uploadez le fichier CSV de consommation

3. **Configurer les clés** :
   - Choisissez le type de clés (Dynamique par défaut, Dynamique, ou Statique)
   - Pour "Dynamique", configurez les priorités et ratios

4. **Calculer** :
   - Cliquez sur "Calculer les clés de répartition"
   - Visualisez le graphique généré
   - Consultez les indicateurs (taux d'autoconsommation, etc.)

---

## 🔄 Migration depuis l'ancienne version

Si vous avez des données existantes :

```bash
# Sauvegardez d'abord vos données
cp textblocks.db textblocks_backup.db
cp -r Courbes Courbes_backup
cp -r Export Export_backup

# Lancez la migration
python migrate_data.py
```

Le script :
- Créera un utilisateur `admin` (mot de passe: `Admin123!`)
- Migrera vos producteurs et consommateurs
- Créera un projet "Données migrées"

---

## 📁 Structure des fichiers

```
RepartKey_UI/
├── app_auth.py          # Application principale
├── models.py            # Modèles de base de données
├── forms.py             # Formulaires
├── config.py            # Configuration
├── migrate_data.py      # Script de migration
├── .env                 # Variables d'environnement (à créer)
├── repartkey.db         # Base de données (créée automatiquement)
├── requirements.txt     # Dépendances Python
├── templates/           # Templates HTML
│   ├── login.html
│   ├── register.html
│   ├── projects.html
│   └── index.html
├── Courbes/            # Fichiers CSV uploadés
└── Export/             # Exports par projet
    ├── project_1/
    ├── project_2/
    └── ...
```

---

## 🛠️ Dépannage rapide

### Erreur "Module not found"
```bash
pip install --upgrade -r requirements.txt
```

### Erreur "Database is locked"
- Fermez toutes les instances de l'application
- Supprimez le fichier `.db-journal` s'il existe

### Erreur de permission (Linux/Mac)
```bash
chmod 755 app_auth.py
chmod -R 777 Courbes Export
```

### Réinitialiser la base de données
```python
python
>>> from app_auth import app, db
>>> with app.app_context():
...     db.drop_all()
...     db.create_all()
>>> exit()
```

---

## 🔒 Sécurité

### En production, TOUJOURS :

1. **Changer la clé secrète** dans `.env` :
```bash
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

2. **Utiliser HTTPS** et activer :
```bash
SESSION_COOKIE_SECURE=True
```

3. **Changer les mots de passe par défaut**

4. **Sauvegarder régulièrement** :
```bash
# Script de sauvegarde quotidienne
cp repartkey.db backups/repartkey_$(date +%Y%m%d).db
```

---

## 📝 Commandes utiles

### Créer un super utilisateur
```python
from app_auth import app, db
from models import User

with app.app_context():
    user = User(username='superadmin', email='admin@example.com')
    user.set_password('SecurePassword123!')
    db.session.add(user)
    db.session.commit()
```

### Lister tous les utilisateurs
```python
from app_auth import app
from models import User

with app.app_context():
    users = User.query.all()
    for u in users:
        print(f"{u.username} - {u.email}")
```

### Supprimer un projet
```python
from app_auth import app, db
from models import Project

with app.app_context():
    project = Project.query.get(1)  # ID du projet
    if project:
        db.session.delete(project)
        db.session.commit()
```

---

## 🆘 Support

En cas de problème :
1. Vérifiez ce guide
2. Consultez `README_AUTH.md` pour plus de détails
3. Vérifiez les logs d'erreur
4. Conservez vos sauvegardes !

---

**Bon usage de RepartElec !** ⚡