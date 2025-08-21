# migrate_data.py - Script pour migrer les données de l'ancienne version

import os
import sys
import sqlite3
import json
import pickle
import shutil
from datetime import datetime

# Ajouter le répertoire courant au path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app_auth import app, db
from models import User, Project, ConsumerBlock, ProducerBlock, ConsumerObject, ProducerObject
import Consumer
import Producer

class DataMigrator:
    def __init__(self, old_db_path='textblocks.db', new_db_path='repartkey.db'):
        self.old_db_path = old_db_path
        self.new_db_path = new_db_path
        self.old_conn = None
        self.admin_user = None
        self.default_project = None
        
    def connect_old_db(self):
        """Connexion à l'ancienne base de données"""
        if not os.path.exists(self.old_db_path):
            print(f"❌ Ancienne base de données '{self.old_db_path}' non trouvée.")
            return False
        
        try:
            self.old_conn = sqlite3.connect(self.old_db_path)
            self.old_conn.row_factory = sqlite3.Row
            print(f"✅ Connexion à l'ancienne base de données réussie")
            return True
        except Exception as e:
            print(f"❌ Erreur de connexion à l'ancienne base : {e}")
            return False
    
    def create_admin_user(self):
        """Créer un utilisateur administrateur par défaut"""
        with app.app_context():
            # Vérifier si un utilisateur admin existe déjà
            existing_admin = User.query.filter_by(username='admin').first()
            if existing_admin:
                print("ℹ️  Utilisateur admin existe déjà")
                self.admin_user = existing_admin
                return True
            
            # Créer le nouvel utilisateur admin
            self.admin_user = User(
                username='admin',
                email='admin@repartkey.local'
            )
            self.admin_user.set_password('Admin123!')  # Mot de passe par défaut
            
            try:
                db.session.add(self.admin_user)
                db.session.commit()
                print("✅ Utilisateur administrateur créé")
                print("   Username: admin")
                print("   Password: Admin123!")
                print("   ⚠️  IMPORTANT: Changez ce mot de passe après la première connexion!")
                return True
            except Exception as e:
                print(f"❌ Erreur lors de la création de l'utilisateur : {e}")
                db.session.rollback()
                return False
    
    def create_migration_project(self):
        """Créer un projet pour les données migrées"""
        with app.app_context():
            if not self.admin_user:
                print("❌ Utilisateur admin non trouvé")
                return False
            
            # Créer le projet de migration
            self.default_project = Project(
                name='Données migrées',
                description='Projet contenant les données migrées depuis l\'ancienne version',
                user_id=self.admin_user.id
            )
            
            try:
                db.session.add(self.default_project)
                db.session.commit()
                print(f"✅ Projet de migration créé (ID: {self.default_project.id})")
                return True
            except Exception as e:
                print(f"❌ Erreur lors de la création du projet : {e}")
                db.session.rollback()
                return False
    
    def migrate_consumer_blocks(self):
        """Migrer les ConsumerBlocks"""
        with app.app_context():
            try:
                cursor = self.old_conn.cursor()
                
                # Récupérer les consumer_blocks de l'ancienne base
                cursor.execute("""
                    SELECT * FROM consumer_block 
                    ORDER BY id
                """)
                old_consumers = cursor.fetchall()
                
                if not old_consumers:
                    print("ℹ️  Aucun ConsumerBlock à migrer")
                    return True
                
                print(f"📦 Migration de {len(old_consumers)} ConsumerBlocks...")
                
                for old_consumer in old_consumers:
                    # Créer le nouveau ConsumerBlock
                    new_consumer = ConsumerBlock(
                        cons_name=old_consumer['cons_name'],
                        project_id=self.default_project.id,
                        date_created=datetime.fromisoformat(old_consumer['date_created']) if old_consumer['date_created'] else datetime.utcnow()
                    )
                    db.session.add(new_consumer)
                    db.session.flush()  # Pour obtenir l'ID
                    
                    # Chercher le ConsumerObject associé dans l'ancienne base
                    cursor.execute("""
                        SELECT * FROM consumer_objects 
                        WHERE consumer_block_id = ?
                    """, (old_consumer['id'],))
                    old_consumer_obj = cursor.fetchone()
                    
                    if old_consumer_obj:
                        # Créer le ConsumerObject
                        new_consumer_obj = ConsumerObject(
                            consumer_block_id=new_consumer.id,
                            consumer_name=old_consumer_obj['consumer_name'],
                            file_path=old_consumer_obj['file_path'] or "",
                            priority_list=old_consumer_obj['priority_list'] or '[]',
                            ratio_list=old_consumer_obj['ratio_list'] or '[]',
                            object_data=old_consumer_obj['object_data']
                        )
                        db.session.add(new_consumer_obj)
                        print(f"  ✅ ConsumerBlock '{new_consumer.cons_name}' migré")
                
                db.session.commit()
                print(f"✅ {len(old_consumers)} ConsumerBlocks migrés avec succès")
                return True
                
            except Exception as e:
                print(f"❌ Erreur lors de la migration des ConsumerBlocks : {e}")
                db.session.rollback()
                return False
    
    def migrate_producer_blocks(self):
        """Migrer les ProducerBlocks"""
        with app.app_context():
            try:
                cursor = self.old_conn.cursor()
                
                # Récupérer les producer_blocks de l'ancienne base
                cursor.execute("""
                    SELECT * FROM producer_block 
                    ORDER BY id
                """)
                old_producers = cursor.fetchall()
                
                if not old_producers:
                    print("ℹ️  Aucun ProducerBlock à migrer")
                    return True
                
                print(f"📦 Migration de {len(old_producers)} ProducerBlocks...")
                
                for old_producer in old_producers:
                    # Créer le nouveau ProducerBlock
                    new_producer = ProducerBlock(
                        prod_name=old_producer['prod_name'],
                        project_id=self.default_project.id,
                        date_created=datetime.fromisoformat(old_producer['date_created']) if old_producer['date_created'] else datetime.utcnow()
                    )
                    db.session.add(new_producer)
                    db.session.flush()  # Pour obtenir l'ID
                    
                    # Chercher le ProducerObject associé dans l'ancienne base
                    cursor.execute("""
                        SELECT * FROM producer_objects 
                        WHERE producer_block_id = ?
                    """, (old_producer['id'],))
                    old_producer_obj = cursor.fetchone()
                    
                    if old_producer_obj:
                        # Créer le ProducerObject
                        new_producer_obj = ProducerObject(
                            producer_block_id=new_producer.id,
                            producer_name=old_producer_obj['producer_name'],
                            file_path=old_producer_obj['file_path'] or "",
                            producer_id_number=old_producer_obj['producer_id_number'] or 1234567901000,
                            object_data=old_producer_obj['object_data']
                        )
                        db.session.add(new_producer_obj)
                        print(f"  ✅ ProducerBlock '{new_producer.prod_name}' migré")
                
                db.session.commit()
                print(f"✅ {len(old_producers)} ProducerBlocks migrés avec succès")
                return True
                
            except Exception as e:
                print(f"❌ Erreur lors de la migration des ProducerBlocks : {e}")
                db.session.rollback()
                return False
    
    def migrate_files(self):
        """Copier les fichiers CSV et exports"""
        try:
            # Migrer les fichiers CSV
            if os.path.exists('Courbes'):
                print("📁 Migration des fichiers CSV...")
                csv_files = [f for f in os.listdir('Courbes') if f.endswith('.csv')]
                if csv_files:
                    print(f"  {len(csv_files)} fichiers CSV trouvés")
                else:
                    print("  Aucun fichier CSV à migrer")
            
            # Créer le dossier d'export pour le projet migré
            if os.path.exists('Export') and self.default_project:
                old_export_files = os.listdir('Export')
                if old_export_files:
                    new_export_dir = f'Export/project_{self.default_project.id}'
                    if not os.path.exists(new_export_dir):
                        os.makedirs(new_export_dir, exist_ok=True)
                    
                    print(f"📁 Migration des fichiers d'export vers {new_export_dir}...")
                    for file in old_export_files:
                        if file.endswith('.csv'):
                            src = os.path.join('Export', file)
                            dst = os.path.join(new_export_dir, file)
                            shutil.copy2(src, dst)
                            print(f"  ✅ {file} copié")
                    
                    print(f"✅ Fichiers d'export migrés")
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors de la migration des fichiers : {e}")
            return False
    
    def run_migration(self):
        """Exécuter la migration complète"""
        print("\n" + "="*60)
        print("🚀 MIGRATION DES DONNÉES VERS LA NOUVELLE VERSION")
        print("="*60 + "\n")
        
        # Vérifier l'existence de la nouvelle base
        if os.path.exists(self.new_db_path):
            response = input(f"⚠️  La base '{self.new_db_path}' existe déjà. Continuer ? (o/n): ")
            if response.lower() != 'o':
                print("❌ Migration annulée")
                return False
        
        # Créer les tables de la nouvelle base
        with app.app_context():
            db.create_all()
            print("✅ Tables de la nouvelle base créées")
        
        # Se connecter à l'ancienne base
        if not self.connect_old_db():
            return False
        
        # Créer l'utilisateur admin
        if not self.create_admin_user():
            return False
        
        # Créer le projet de migration
        if not self.create_migration_project():
            return False
        
        # Migrer les données
        success = True
        success = success and self.migrate_consumer_blocks()
        success = success and self.migrate_producer_blocks()
        success = success and self.migrate_files()
        
        # Fermer la connexion
        if self.old_conn:
            self.old_conn.close()
        
        if success:
            print("\n" + "="*60)
            print("✅ MIGRATION TERMINÉE AVEC SUCCÈS!")
            print("="*60)
            print("\n📋 Résumé:")
            print(f"  • Utilisateur créé: admin")
            print(f"  • Mot de passe: Admin123!")
            print(f"  • Projet créé: {self.default_project.name if self.default_project else 'N/A'}")
            print("\n⚠️  IMPORTANT:")
            print("  1. Changez le mot de passe admin après la première connexion")
            print("  2. Sauvegardez l'ancienne base de données 'textblocks.db'")
            print("  3. Testez l'application avant de supprimer les anciennes données")
            print("\n🌐 Lancez l'application avec: python app_auth.py")
        else:
            print("\n❌ Migration échouée. Vérifiez les erreurs ci-dessus.")
        
        return success


def main():
    """Fonction principale"""
    print("Bienvenue dans l'outil de migration RepartKey")
    print("-" * 40)
    
    # Créer une sauvegarde
    if os.path.exists('textblocks.db'):
        backup_name = f'textblocks_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        try:
            shutil.copy2('textblocks.db', backup_name)
            print(f"✅ Sauvegarde créée: {backup_name}")
        except Exception as e:
            print(f"⚠️  Impossible de créer la sauvegarde: {e}")
            response = input("Continuer sans sauvegarde ? (o/n): ")
            if response.lower() != 'o':
                print("Migration annulée")
                return
    
    # Lancer la migration
    migrator = DataMigrator()
    migrator.run_migration()


if __name__ == '__main__':
    main()