# forms.py - Formulaires Flask-WTF pour l'authentification

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from models import User
import random


class CaptchaField(IntegerField):
    """Champ personnalisé pour le CAPTCHA mathématique"""
    pass


class LoginForm(FlaskForm):
    username = StringField('Nom d\'utilisateur', validators=[
        DataRequired(message='Le nom d\'utilisateur est requis')
    ])
    password = PasswordField('Mot de passe', validators=[
        DataRequired(message='Le mot de passe est requis')
    ])
    captcha_answer = IntegerField('Réponse au CAPTCHA', validators=[
        DataRequired(message='Veuillez répondre au CAPTCHA')
    ])
    submit = SubmitField('Se connecter')


class RegistrationForm(FlaskForm):
    username = StringField('Nom d\'utilisateur', validators=[
        DataRequired(message='Le nom d\'utilisateur est requis'),
        Length(min=3, max=80, message='Le nom d\'utilisateur doit contenir entre 3 et 80 caractères')
    ])
    email = StringField('Email', validators=[
        DataRequired(message='L\'email est requis'),
        Email(message='Email invalide')
    ])
    password = PasswordField('Mot de passe', validators=[
        DataRequired(message='Le mot de passe est requis'),
        Length(min=6, message='Le mot de passe doit contenir au moins 6 caractères')
    ])
    password2 = PasswordField('Confirmer le mot de passe', validators=[
        DataRequired(message='Veuillez confirmer le mot de passe'),
        EqualTo('password', message='Les mots de passe ne correspondent pas')
    ])
    captcha_answer = IntegerField('Réponse au CAPTCHA', validators=[
        DataRequired(message='Veuillez répondre au CAPTCHA')
    ])
    submit = SubmitField('S\'inscrire')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Ce nom d\'utilisateur est déjà pris. Veuillez en choisir un autre.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Cet email est déjà enregistré. Veuillez en utiliser un autre.')


class ProjectForm(FlaskForm):
    name = StringField('Nom du projet', validators=[
        DataRequired(message='Le nom du projet est requis'),
        Length(min=1, max=100, message='Le nom doit contenir entre 1 et 100 caractères')
    ])
    description = TextAreaField('Description', validators=[
        Length(max=500, message='La description ne peut pas dépasser 500 caractères')
    ])
    submit = SubmitField('Créer le projet')


class CaptchaHelper:
    """Classe utilitaire pour générer et valider les CAPTCHAs mathématiques"""
    
    @staticmethod
    def generate_captcha():
        """Génère une question CAPTCHA mathématique simple"""
        operations = [
            ('+', lambda a, b: a + b),
            ('-', lambda a, b: a - b),
            ('×', lambda a, b: a * b)
        ]
        
        op_symbol, op_func = random.choice(operations)
        
        if op_symbol == '×':
            # Pour la multiplication, utiliser des nombres plus petits
            num1 = random.randint(2, 9)
            num2 = random.randint(2, 9)
        elif op_symbol == '-':
            # Pour la soustraction, s'assurer que le résultat est positif
            num1 = random.randint(10, 20)
            num2 = random.randint(1, num1)
        else:
            # Pour l'addition
            num1 = random.randint(1, 20)
            num2 = random.randint(1, 20)
        
        question = f"{num1} {op_symbol} {num2} = ?"
        answer = op_func(num1, num2)
        
        return question, answer