#!/usr/bin/env python3
# migrate_consumer_fields.py - Script de migration pour ajouter les champs PRM et tarifs

import os
import sys
import sqlite3
from datetime import datetime

def get_db_path():
    """Obtenir le chemin vers la base de données"""
    # Chercher d'abord repartkey.db (nouvelle version)
    if os.path.exists('repartkey.db'):
        return 'repartkey.db'
    # Puis textblocks.db (ancienne version)
    elif os.path.exists('textblocks.db'):
        return 'textblocks.db'
    else:
        print("❌ Aucune base de données trouvée (repartkey.db ou textblocks.db)")
        return None

def backup_database(db_path):
    """Créer une sauvegarde de la base de données"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{db_path.replace('.db', '')}_backup_{timestamp}.db"
    
    try:
        import shutil
        shutil.copy2(db_path, backup_name)
        print(f"✅ Sauvegarde créée: {backup_name}")
        return backup_name
    except Exception as e:
        print(f"⚠️  Impossible de créer la sauvegarde: {e}")
        return None

def check_table_exists(cursor, table_name):
    """Vérifier si une table existe"""
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name=?
    """, (table_name,))
    return cursor.fetchone() is not None

def get_table_columns(cursor, table_name):
    """Obtenir la liste des colonnes d'une table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    return [col[1] for col in columns]  # col[1] est le nom de la colonne

def add_column_if_not_exists(cursor, table_name, column_name, column_type, default_value=None):
    """Ajouter une colonne si elle n'existe pas déjà"""
    columns = get_table_columns(cursor, table_name)
    
    if column_name in columns:
        print(f"  ℹ️  Colonne '{column_name}' existe déjà")
        return False
    
    try:
        sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        if default_value is not None:
            sql += f" DEFAULT {default_value}"
        
        cursor.execute(sql)
        print(f"  ✅ Colonne '{column_name}' ajoutée")
        return True
    except Exception as e:
        print(f"  ❌ Erreur lors de l'ajout de '{column_name}': {e}")
        return False

def migrate_consumer_blocks(cursor):
    """Migrer la table consumer_blocks"""
    print("\n🔧 Migration de la table consumer_blocks...")
    
    if not check_table_exists(cursor, 'consumer_blocks'):
        print("  ❌ Table 'consumer_blocks' non trouvée")
        return False
    
    columns_added = 0
    
    # Ajouter le champ PRM
    if add_column_if_not_exists(cursor, 'consumer_blocks', 'prm', 'VARCHAR(50)'):
        columns_added += 1
    
    # Ajouter le champ type de tarif
    if add_column_if_not_exists(cursor, 'consumer_blocks', 'tarif_type', 'VARCHAR(10)', "'normal'"):
        columns_added += 1
    
    # Ajouter les champs de tarifs
    if add_column_if_not_exists(cursor, 'consumer_blocks', 'tarif_normal', 'FLOAT', '0.0'):
        columns_added += 1
    
    if add_column_if_not_exists(cursor, 'consumer_blocks', 'tarif_hc', 'FLOAT', '0.0'):
        columns_added += 1
    
    if add_column_if_not_exists(cursor, 'consumer_blocks', 'tarif_hp', 'FLOAT', '0.0'):
        columns_added += 1
    
    print(f"  📊 {columns_added} nouvelle(s) colonne(s) ajoutée(s)")
    return True

def verify_migration(cursor):
    """Vérifier que la migration s'est bien déroulée"""
    print("\n🔍 Vérification de la migration...")
    
    expected_columns = ['prm', 'tarif_type', 'tarif_normal', 'tarif_hc', 'tarif_hp']
    columns = get_table_columns(cursor, 'consumer_blocks')
    
    missing_columns = []
    for col in expected_columns:
        if col not in columns:
            missing_columns.append(col)
    
    if missing_columns:
        print(f"  ❌ Colonnes manquantes: {', '.join(missing_columns)}")
        return False
    else:
        print("  ✅ Toutes les colonnes sont présentes")
        
    # Vérifier les données
    cursor.execute("SELECT COUNT(*) FROM consumer_blocks")
    count = cursor.fetchone()[0]
    print(f"  📊 {count} consommateur(s) dans la base")
    
    return True

def show_table_structure(cursor):
    """Afficher la structure de la table après migration"""
    print("\n📋 Structure finale de la table consumer_blocks:")
    
    cursor.execute("PRAGMA table_info(consumer_blocks)")
    columns = cursor.fetchall()
    
    print("  +----+-------------------+-------------+-----------+")
    print("  | ID | Nom               | Type        | Défaut    |")
    print("  +----+-------------------+-------------+-----------+")
    
    for col in columns:
        col_id = str(col[0]).ljust(2)
        name = str(col[1]).ljust(17)
        col_type = str(col[2]).ljust(11)
        default = str(col[4] or '').ljust(9)
        print(f"  | {col_id} | {name} | {col_type} | {default} |")
    
    print("  +----+-------------------+-------------+-----------+")

def main():
    """Fonction principale"""
    print("=" * 60)
    print("🔄 MIGRATION DES CHAMPS CONSOMMATEUR")
    print("=" * 60)
    print("Ce script ajoute les nouveaux champs PRM et tarifs")
    print("aux consommateurs existants.")
    print()
    
    # Trouver la base de données
    db_path = get_db_path()
    if not db_path:
        return False
    
    print(f"📂 Base de données trouvée: {db_path}")
    
    # Créer une sauvegarde
    backup_path = backup_database(db_path)
    if not backup_path:
        response = input("Continuer sans sauvegarde ? (o/n): ")
        if response.lower() != 'o':
            print("❌ Migration annulée")
            return False
    
    # Effectuer la migration
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Migrer les tables
        success = migrate_consumer_blocks(cursor)
        
        if success:
            # Valider les changements
            conn.commit()
            
            # Vérifier la migration
            if verify_migration(cursor):
                show_table_structure(cursor)
                
                print("\n" + "=" * 60)
                print("✅ MIGRATION TERMINÉE AVEC SUCCÈS!")
                print("=" * 60)
                print("\n📋 Résumé des changements:")
                print("  • Champ PRM ajouté (numéro de compteur)")
                print("  • Champ tarif_type ajouté (normal/hp_hc)")
                print("  • Champs tarifs ajoutés (normal, HP, HC)")
                print("\n🚀 Vous pouvez maintenant:")
                print("  1. Redémarrer l'application")
                print("  2. Éditer vos consommateurs pour remplir les nouveaux champs")
                print("  3. Configurer les tarifs selon vos besoins")
                
                if backup_path:
                    print(f"\n💾 Sauvegarde conservée: {backup_path}")
                
                return True
            else:
                print("\n❌ Erreur lors de la vérification")
                conn.rollback()
        else:
            print("\n❌ Erreur lors de la migration")
            conn.rollback()
            
    except Exception as e:
        print(f"\n❌ Erreur lors de la migration: {e}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()
    
    return False

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Migration interrompue par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        sys.exit(1)