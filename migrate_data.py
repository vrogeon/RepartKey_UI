from app_auth import app, db
from models import Project  # Importez le modèle concerné


def migrate_repartition_key_type():
    """
    Met à jour les données existantes avec une valeur par défaut pour repartition_key_type
    """
    try:
        # Valeur par défaut pour les enregistrements existants
        default_key_type = "default"  # Adaptez selon votre logique métier

        # Mettre à jour tous les enregistrements sans valeur pour repartition_key_type
        repartitions = Project.query.filter(Project.repartition_key_type.is_(None)).all()

        for repartition in repartitions:
            repartition.repartition_key_type = default_key_type

        db.session.commit()
        print(f"Migration réussie: {len(repartitions)} enregistrements mis à jour.")
    except Exception as e:
        db.session.rollback()
        print(f"Erreur lors de la migration: {str(e)}")


if __name__ == "__main__":
    # Création du contexte d'application Flask
    with app.app_context():
        migrate_repartition_key_type()
