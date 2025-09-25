from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Importation de votre application et de votre db
from app_auth import app, db
import models  # Pour s'assurer que tous les modèles sont chargés

# Initialisation de Flask-Migrate
migrate = Migrate(app, db)
