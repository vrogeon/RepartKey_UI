# Changelog - Mise à jour RepartKey

## Version 2.1.0 - Amélioration Mode Démo et Nouveaux Champs Consommateur

### 🎯 Mode Démo Amélioré

#### Changements visuels
- **Nouveau bandeau démo** : Remplacement de la popup par un bandeau intégré dans le sidebar
- **Design cohérent** : Le bandeau démo utilise le même style que les projets normaux
- **Navigation simplifiée** : Bouton "← Connexion" pour revenir au mode authentifié
- **Couleurs distinctives** : Bandeau vert pour bien identifier le mode démonstration

#### Fonctionnalités corrigées
- **Affichage des données** : Le graphique en mode démo fonctionne maintenant comme en mode connecté
- **Calcul des clés** : Les calculs de répartition fonctionnent correctement en mode démo
- **Upload de fichiers** : Support complet de l'upload de fichiers CSV
- **Statistiques** : Affichage correct des indicateurs (taux d'autoconsommation, etc.)
- **Nettoyage automatique** : Suppression des données temporaires à la fermeture

### 📋 Nouveaux Champs Consommateur

#### Champ PRM (Point de Référence et de Mesure)
- **Ajout du champ PRM** dans l'édition des consommateurs
- **Position** : Sous le nom du consommateur
- **Format** : Texte libre pour le numéro de série du compteur
- **Sauvegarde** : Stocké en base de données

#### Système de Tarification
- **Toggle HP/HC** : Basculement entre tarif normal et heures pleines/creuses
- **Interface intuitive** : Switch visuel avec labels "Normal" et "HP/HC"
- **Champs conditionnels** :
  - Mode Normal : 1 champ (Tarif normal)
  - Mode HP/HC : 3 champs (Tarif normal, Heure creuse, Heure pleine)
- **Validation** : Vérification que les tarifs ne sont pas négatifs
- **Responsive** : Adaptation mobile de l'interface

### 🛠️ Modifications Techniques

#### Base de données
- **Nouveaux champs dans `consumer_blocks`** :
  - `prm` (VARCHAR(50)) : Numéro PRM
  - `tarif_type` (VARCHAR(10)) : Type de tarif ('normal' ou 'hp_hc')
  - `tarif_normal` (FLOAT) : Tarif normal en €/kWh
  - `tarif_hc` (FLOAT) : Tarif heure creuse en €/kWh
  - `tarif_hp` (FLOAT) : Tarif heure pleine en €/kWh

#### Migration automatique
- **Auto-migration** : Ajout automatique des colonnes au démarrage de l'application
- **Valeurs par défaut** : Initialisation correcte des nouveaux champs
- **Compatibilité** : Support des bases existantes sans perte de données

#### Interface utilisateur
- **Template mis à jour** : Nouvelle interface d'édition des consommateurs
- **Validation JavaScript** : Contrôles côté client pour l'expérience utilisateur
- **Styles CSS** : Nouveaux styles pour le toggle et les champs de tarifs

### 🔧 Scripts de Migration

#### `migrate_consumer_fields.py`
- **Migration sécurisée** : Sauvegarde automatique avant modification
- **Vérification** : Contrôle de l'intégrité après migration
- **Affichage détaillé** : Structure de la table après migration
- **Gestion d'erreurs** : Rollback automatique en cas de problème

### 📁 Fichiers Modifiés

#### Backend Python
- `models.py` : Ajout des nouveaux champs dans ConsumerBlock
- `app_auth.py` : 
  - Migration automatique des colonnes
  - Support mode démo amélioré
  - Route de mise à jour des consommateurs étendue

#### Templates HTML
- `templates/update_consumer.html` : Nouvelle interface avec PRM et tarifs
- `templates/index.html` : Bandeau démo intégré dans le sidebar

#### Scripts utilitaires
- `migrate_consumer_fields.py` : Script de migration manuel

### 🚀 Installation et Migration

#### Pour les nouvelles installations
Les nouveaux champs sont créés automatiquement lors de la première exécution.

#### Pour les installations existantes
```bash
# Option 1 : Migration automatique (recommandée)
python app_auth.py  # Les colonnes sont ajoutées automatiquement

# Option 2 : Migration manuelle
python migrate_consumer_fields.py
```

### 🎮 Utilisation

#### Mode Démo
1. Accédez à `/demo`
2. Utilisez le bandeau "MODE DÉMONSTRATION" pour vous repérer
3. Cliquez sur "← Connexion" pour revenir au mode authentifié
4. Toutes les fonctionnalités sont disponibles (upload, calcul, graphique)

#### Nouveaux Champs Consommateur
1. Éditez un consommateur existant
2. Remplissez le champ PRM si disponible
3. Choisissez le type de tarif avec le toggle
4. Saisissez les tarifs selon le mode choisi
5. Validez pour sauvegarder

### 🐛 Corrections de Bugs

- **Mode démo** : Affichage correct des données et graphiques
- **Upload fichiers** : Fonctionnement en mode démo
- **Calculs** : Résultats cohérents entre modes normal et démo
- **Navigation** : Retour correct depuis les pages d'édition
- **Responsive** : Interface adaptée aux petits écrans

### ⚠️ Notes de Compatibilité

- **Base de données** : Compatible avec les anciennes versions
- **Navigateurs** : Support des navigateurs modernes (ES6+)
- **Fichiers CSV** : Format inchangé, compatibilité totale
- **API** : Endpoints existants non modifiés

### 📊 Performances

- **Chargement** : Migration automatique sans impact sur le démarrage
- **Mémoire** : Mode démo optimisé avec nettoyage automatique
- **Réseau** : Aucune requête supplémentaire pour les nouvelles fonctionnalités

---

**Date de version** : 2024-12-19
**Compatibilité** : Python 3.8+, SQLite 3.x