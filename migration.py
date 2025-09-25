from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Importation de votre application et de votre db
from app_auth import app, db
# from models import PrioritySettings, Project  # Pour s'assurer que tous les modèles sont chargés
import models  # Pour s'assurer que tous les modèles sont chargés

# Initialisation de Flask-Migrate
migrate = Migrate(app, db)
