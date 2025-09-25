from app_auth import app, db
from models import Project, PrioritySettings


def init_default_priority_settings():
    """
    Initialise les paramètres de priorité par défaut pour tous les projets existants
    """
    try:
        projects = Project.query.all()
        producers = ["EDF", "ENGIE", "TOTAL"]  # Ajustez selon vos producteurs
        priorities = [1, 2, 3]  # Ajustez selon vos priorités

        for project in projects:
            # Vérifier si le projet a déjà des paramètres
            existing_settings = PrioritySettings.query.filter_by(project_id=project.id).first()
            if not existing_settings:
                # Créer des paramètres par défaut (tous activés)
                for producer in producers:
                    for priority in priorities:
                        setting = PrioritySettings(
                            project_id=project.id,
                            producer=producer,
                            priority=priority,
                            enabled=True
                        )
                        db.session.add(setting)

        db.session.commit()
        print(f"Migration réussie: paramètres de priorité initialisés pour {len(projects)} projets.")
    except Exception as e:
        db.session.rollback()
        print(f"Erreur lors de la migration: {str(e)}")


if __name__ == "__main__":
    # Création du contexte d'application Flask
    with app.app_context():
        init_default_priority_settings()
