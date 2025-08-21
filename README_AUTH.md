# RepartKey_UI - Guide de migration vers la version avec authentification

## 🚀 Nouvelles fonctionnalités

Cette version améliorée de RepartKey_UI inclut :

- **Système d'authentification complet** : Création de compte, connexion sécurisée avec mot de passe
- **CAPTCHA mathématique** : Protection contre les bots lors de l'inscription et la connexion
- **Gestion multi-projets** : Chaque utilisateur peut créer et gérer plusieurs projets indépendants
- **Isolation des données** : Les données de chaque projet sont sauvegardées séparément
- **Interface utilisateur améliorée** : Nouveau design moderne pour la gestion des projets

## 📋 Prérequis

- Python 3.8 ou supérieur
- pip (gestionnaire de paquets Python)

## 🛠️ Installation

### 1. Sauvegarde de vos données existantes

**IMPORTANT** : Avant de migrer, sauvegardez votre base de données et vos fichiers :

```bash
# Créer un dossier de sauvegarde
mkdir backup_repartkey

# Copier la base de données existante
cp textblocks.db backup_repartkey/

# Copier les dossiers de données
cp -r Courbes backup_repartkey/
cp -r Export backup_repartkey/
```

### 2. Installation des nouvelles dépendances

```bash
# Installer les nouvelles dépendances
pip install -r requirements.txt
```

### 3. Création de la structure de fichiers

Créez les nouveaux fichiers dans votre projet :

1. **models.py** : Contient tous les modèles de base de données
2. **forms.py** : Contient les formulaires Flask-WTF
3. **app_auth.py** : Nouvelle version de l'application avec authentification
4. Créez un dossier `templates` et ajoutez :
   - **login.html**
   - **register.html**
   - **projects.html**

### 4. Migration de la base de données

La nouvelle version utilise une base de données différente (`repartkey.db` au lieu de `textblocks.db`).

#### Option A : Nouvelle installation (recommandé pour commencer)

```python
# Créer la nouvelle base de données
python
>>> from app_auth import app, db
>>> with app.app_context():
...     db.create_all()
>>> exit()
```

#### Option B : Migration des données existantes (optionnel)

Si vous souhaitez conserver vos données existantes, créez ce script de migration :

```python
# migrate_data.py
from app_auth import app, db
from models import User, Project, ConsumerBlock, ProducerBlock
import sqlite3

def migrate_data():
    with app.app_context():
        # Créer les nouvelles tables
        db.create_all()
        
        # Créer un utilisateur par défaut
        user = User(username='admin', email='admin@example.com')
        user.set_password('admin123')  # Changez ce mot de passe !
        db.session.add(user)
        db.session.commit()
        
        # Créer un projet par défaut
        project = Project(
            name='Projet migré',
            description='Données migrées depuis l\'ancienne version',
            user_id=user.id
        )
        db.session.add(project)
        db.session.commit()
        
        # Ici, vous pouvez ajouter le code pour migrer vos données existantes
        # depuis textblocks.db vers le nouveau projet
        
        print(f"Migration terminée !")
        print(f"Utilisateur créé : admin")
        print(f"Mot de passe : admin123 (pensez à le changer)")

if __name__ == '__main__':
    migrate_data()
```

### 5. Configuration

Modifiez la clé secrète dans `app_auth.py` :

```python
app.config['SECRET_KEY'] = 'votre-clé-secrète-unique-et-complexe'
```

### 6. Mise à jour du template index.html

Votre template `index.html` existant doit être légèrement modifié pour fonctionner avec les projets :

1. Ajoutez en haut du template après le bloc content :
```html
{% if project %}
<div style="background: #e0f2fe; padding: 10px; margin-bottom: 20px; border-radius: 8px;">
    <strong>Projet actuel :</strong> {{ project.name }}
    <a href="{{ url_for('projects') }}" style="float: right;">← Retour aux projets</a>
</div>
{% endif %}
```

2. Modifiez les URLs des formulaires pour inclure le project_id :
```javascript
// Remplacez les URL existantes par :
const url = buildUrl(`/project/${projectId}/add_consumer`);
const url = buildUrl(`/project/${projectId}/add_producer`);
const url = buildUrl(`/project/${projectId}/compute_repartition_keys`);
const dataUrl = buildUrl(`/project/${projectId}/data`);
```

## 🚀 Lancement de l'application

### En développement

```bash
python app_auth.py
```

L'application sera accessible à : http://localhost:5000

### En production (cPanel)

1. Renommez `app_auth.py` en `app.py` (remplace l'ancien)
2. Configurez votre fichier `.htaccess` comme avant
3. Assurez-vous que tous les fichiers ont les bonnes permissions

## 👤 Utilisation

### Premier accès

1. Accédez à l'application
2. Cliquez sur "Pas encore de compte ? S'inscrire"
3. Créez votre compte avec :
   - Un nom d'utilisateur unique
   - Une adresse email valide
   - Un mot de passe (minimum 6 caractères)
   - Répondez au CAPTCHA mathématique

### Création d'un projet

1. Connectez-vous avec vos identifiants
2. Cliquez sur "➕ Nouveau Projet"
3. Donnez un nom et une description (optionnelle) à votre projet
4. Cliquez sur "Créer le projet"

### Utilisation d'un projet

Une fois dans un projet, l'interface fonctionne comme avant :
- Ajoutez des producteurs et consommateurs
- Uploadez les fichiers CSV
- Configurez les priorités et ratios
- Calculez les clés de répartition

Chaque projet garde ses données séparées des autres.

## 🔒 Sécurité

### Recommandations importantes

1. **Changez la clé secrète** dans `app_auth.py`
2. **Utilisez des mots de passe forts** pour les comptes utilisateurs
3. **Sauvegardez régulièrement** la base de données `repartkey.db`
4. **En production**, utilisez HTTPS pour sécuriser les connexions

### Structure des données

Les données sont maintenant organisées ainsi :
```
RepartKey_UI/
├── repartkey.db          # Base de données principale
├── Courbes/              # Fichiers CSV uploadés
│   └── [fichiers.csv]
└── Export/               # Fichiers exportés par projet
    ├── project_1/        # Données du projet 1
    ├── project_2/        # Données du projet 2
    └── ...
```

## 🐛 Dépannage

### Problème : "Module not found"

```bash
pip install --upgrade -r requirements.txt
```

### Problème : Base de données corrompue

Restaurez depuis votre sauvegarde :
```bash
cp backup_repartkey/textblocks.db ./
```

### Problème : Permissions sur cPanel

```bash
chmod 755 app.py
chmod 755 -R templates/
chmod 777 -R Courbes/
chmod 777 -R Export/
```

## 📝 Notes de migration

### Différences principales avec l'ancienne version

1. **Base de données** : `repartkey.db` au lieu de `textblocks.db`
2. **Routes** : Les routes incluent maintenant `/project/<project_id>/`
3. **Authentification** : Toutes les routes nécessitent une connexion
4. **Structure** : Code réorganisé en modules séparés (models.py, forms.py)

### Retour à l'ancienne version

Si nécessaire, vous pouvez revenir à l'ancienne version :
```bash
# Restaurer l'ancien app.py
cp backup_repartkey/app.py ./

# Restaurer l'ancienne base de données
cp backup_repartkey/textblocks.db ./
```

## 📧 Support

En cas de problème lors de la migration, conservez vos sauvegardes et n'hésitez pas à demander de l'aide.

---

**Version** : 2.0.0 avec authentification
**Date** : 2024