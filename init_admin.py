# init_admin.py - Script pour créer un utilisateur administrateur

import os
import sys
import getpass
from datetime import datetime

# Ajouter le répertoire courant au path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app_auth import app, db
from models import User, Project

def validate_email(email):
    """Validation basique d'email"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validation du mot de passe"""
    if len(password) < 6:
        return False, "Le mot de passe doit contenir au moins 6 caractères"
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    
    if not (has_upper and has_lower and has_digit):
        return False, "Le mot de passe doit contenir au moins une majuscule, une minuscule et un chiffre"
    
    return True, "OK"

def create_admin_user():
    """Créer un utilisateur administrateur interactivement"""
    
    print("\n" + "="*60)
    print("🔧 CRÉATION D'UN UTILISATEUR ADMINISTRATEUR")
    print("="*60)
    print()
    
    with app.app_context():
        # Vérifier si la base de données existe
        try:
            existing_users = User.query.count()
            if existing_users > 0:
                print(f"ℹ️  Il y a déjà {existing_users} utilisateur(s) dans la base de données.")
                response = input("Voulez-vous créer un nouvel administrateur ? (o/n): ")
                if response.lower() != 'o':
                    print("Création annulée.")
                    return
        except:
            print("📦 Création de la base de données...")
            db.create_all()
            print("✅ Base de données créée")
        
        print("\nVeuillez entrer les informations du nouvel administrateur:\n")
        
        # Demander le nom d'utilisateur
        while True:
            username = input("Nom d'utilisateur (min. 3 caractères): ").strip()
            if len(username) < 3:
                print("❌ Le nom d'utilisateur doit contenir au moins 3 caractères")
                continue
            
            # Vérifier si l'utilisateur existe déjà
            existing = User.query.filter_by(username=username).first()
            if existing:
                print(f"❌ L'utilisateur '{username}' existe déjà")
                continue
            
            break
        
        # Demander l'email
        while True:
            email = input("Adresse email: ").strip()
            if not validate_email(email):
                print("❌ Email invalide")
                continue
            
            # Vérifier si l'email existe déjà
            existing = User.query.filter_by(email=email).first()
            if existing:
                print(f"❌ L'email '{email}' est déjà utilisé")
                continue
            
            break
        
        # Demander le mot de passe
        while True:
            print("\nExigences du mot de passe:")
            print("  • Au moins 6 caractères")
            print("  • Au moins une majuscule")
            print("  • Au moins une minuscule")
            print("  • Au moins un chiffre")
            
            password = getpass.getpass("Mot de passe: ")
            
            valid, message = validate_password(password)
            if not valid:
                print(f"❌ {message}")
                continue
            
            password_confirm = getpass.getpass("Confirmer le mot de passe: ")
            
            if password != password_confirm:
                print("❌ Les mots de passe ne correspondent pas")
                continue
            
            break
        
        # Créer l'utilisateur
        try:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            print("\n" + "="*60)
            print("✅ UTILISATEUR ADMINISTRATEUR CRÉÉ AVEC SUCCÈS!")
            print("="*60)
            print(f"\n📋 Récapitulatif:")
            print(f"  • Nom d'utilisateur: {username}")
            print(f"  • Email: {email}")
            print(f"  • Date de création: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            
            # Proposer de créer un projet de démonstration
            print("\n" + "-"*40)
            response = input("\nVoulez-vous créer un projet de démonstration ? (o/n): ")
            if response.lower() == 'o':
                project_name = input("Nom du projet (par défaut: 'Mon premier projet'): ").strip()
                if not project_name:
                    project_name = "Mon premier projet"
                
                project = Project(
                    name=project_name,
                    description="Projet de démonstration créé automatiquement",
                    user_id=user.id
                )
                db.session.add(project)
                db.session.commit()
                
                print(f"✅ Projet '{project_name}' créé avec succès!")
            
            print("\n" + "="*60)
            print("🚀 VOUS POUVEZ MAINTENANT VOUS CONNECTER!")
            print("="*60)
            print("\nPour lancer l'application:")
            print("  python app_auth.py")
            print("\nPuis ouvrez votre navigateur à:")
            print("  http://localhost:5000")
            print("\n")
            
        except Exception as e:
            print(f"\n❌ Erreur lors de la création de l'utilisateur: {e}")
            db.session.rollback()
            return


def list_users():
    """Lister tous les utilisateurs existants"""
    with app.app_context():
        users = User.query.all()
        
        if not users:
            print("Aucun utilisateur dans la base de données.")
            return
        
        print("\n" + "="*60)
        print("👥 LISTE DES UTILISATEURS")
        print("="*60)
        print()
        print(f"{'ID':<5} {'Nom d utilisateur':<20} {'Email':<30} {'Créé le':<20}")
        print("-"*80)
        
        for user in users:
            created = user.date_created.strftime('%d/%m/%Y %H:%M') if user.date_created else 'N/A'
            print(f"{user.id:<5} {user.username:<20} {user.email:<30} {created:<20}")
        
        print()
        print(f"Total: {len(users)} utilisateur(s)")
        print()


def reset_password():
    """Réinitialiser le mot de passe d'un utilisateur"""
    with app.app_context():
        print("\n" + "="*60)
        print("🔐 RÉINITIALISATION DE MOT DE PASSE")
        print("="*60)
        print()
        
        username = input("Nom d'utilisateur: ").strip()
        user = User.query.filter_by(username=username).first()
        
        if not user:
            print(f"❌ Utilisateur '{username}' non trouvé")
            return
        
        print(f"✅ Utilisateur trouvé: {user.email}")
        
        while True:
            password = getpass.getpass("Nouveau mot de passe: ")
            valid, message = validate_password(password)
            if not valid:
                print(f"❌ {message}")
                continue
            
            password_confirm = getpass.getpass("Confirmer le nouveau mot de passe: ")
            if password != password_confirm:
                print("❌ Les mots de passe ne correspondent pas")
                continue
            
            break
        
        try:
            user.set_password(password)
            db.session.commit()
            print(f"✅ Mot de passe réinitialisé avec succès pour '{username}'")
        except Exception as e:
            print(f"❌ Erreur: {e}")
            db.session.rollback()


def main():
    """Menu principal"""
    while True:
        print("\n" + "="*60)
        print("🔧 GESTIONNAIRE D'UTILISATEURS REPARTKEY")
        print("="*60)
        print("\n1. Créer un nouvel administrateur")
        print("2. Lister tous les utilisateurs")
        print("3. Réinitialiser un mot de passe")
        print("4. Quitter")
        print()
        
        choice = input("Votre choix (1-4): ").strip()
        
        if choice == '1':
            create_admin_user()
        elif choice == '2':
            list_users()
        elif choice == '3':
            reset_password()
        elif choice == '4':
            print("\nAu revoir!")
            break
        else:
            print("❌ Choix invalide")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterruption par l'utilisateur.")
        sys.exit(0)