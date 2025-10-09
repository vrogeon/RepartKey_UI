# app_auth.py - Version avec authentification, gestion de projets et mode démo

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import sys
import json
import pickle
import random

# Import des modèles et formulaires
from models import db, User, Project, TextBlock, ConsumerBlock, ProducerBlock, ConsumerObject, ProducerObject, PrioritySettings
from forms import LoginForm, RegistrationForm, ProjectForm, CaptchaHelper

# Import des modules métier existants
import Consumer
import Producer
import Repartition
import Graph

import plotly.graph_objects as go
import plotly.utils

import uuid
import shutil
from flask import make_response

# Configuration pour le mode démo
DEMO_PROJECT_ID = -1
DEMO_SESSIONS = {}  # Stockage des sessions démo temporaires


def cleanup_demo_session(session_id):
    """Nettoyer les données d'une session démo"""
    if session_id in DEMO_SESSIONS:
        demo_data = DEMO_SESSIONS[session_id]

        # Supprimer les fichiers uploadés
        demo_folder = os.path.join(UPLOAD_FOLDER, f'demo_{session_id}')
        if os.path.exists(demo_folder):
            shutil.rmtree(demo_folder)

        # Supprimer les fichiers d'export
        export_folder = os.path.join(EXPORT_FOLDER, f'demo_{session_id}')
        if os.path.exists(export_folder):
            shutil.rmtree(export_folder)

        # Supprimer de la mémoire
        del DEMO_SESSIONS[session_id]


# Configuration pour l'environnement de production
def setup_paths():
    """Configure les chemins pour l'environnement de production"""
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'Courbes')
    EXPORT_FOLDER = os.path.join(BASE_DIR, 'Export')

    UPLOAD_FOLDER = os.path.normpath(UPLOAD_FOLDER)
    EXPORT_FOLDER = os.path.normpath(EXPORT_FOLDER)

    # Créer les dossiers s'ils n'existent pas
    try:
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER, mode=0o755, exist_ok=True)
            print(f"Upload folder created at: {UPLOAD_FOLDER}")

        if not os.path.exists(EXPORT_FOLDER):
            os.makedirs(EXPORT_FOLDER, mode=0o755, exist_ok=True)
            print(f"Export folder created at: {EXPORT_FOLDER}")

    except Exception as e:
        print(f"Error creating directories: {e}")

    return UPLOAD_FOLDER, EXPORT_FOLDER


# Initialiser les chemins
UPLOAD_FOLDER, EXPORT_FOLDER = setup_paths()

# Configuration de l'application
app = Flask(__name__)

# Configuration de la base de données et de la sécurité
app.config[
    'SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), "repartkey.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limite à 16MB
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production-2024'  # À changer en production

# Initialiser les extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'
login_manager.login_message_category = 'error'

# Extensions de fichiers autorisées
ALLOWED_EXTENSIONS = {'csv'}

# Variables globales pour les statistiques (par projet maintenant)
project_stats = {}

# Configuration pour le mode démo
DEMO_PROJECT_ID = -1  # ID spécial pour le projet démo


# Fonction de chargement de l'utilisateur pour Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Créer les tables de la base de données avec migration
with app.app_context():
    # Créer toutes les tables
    db.create_all()

    # Migration pour ajouter les nouveaux champs aux consommateurs existants
    try:
        # Vérifier si les colonnes existent déjà
        inspector = db.inspect(db.engine)
        consumer_columns = [col['name'] for col in inspector.get_columns('consumer_blocks')]

        # Ajouter les colonnes manquantes
        if 'prm' not in consumer_columns:
            db.engine.execute('ALTER TABLE consumer_blocks ADD COLUMN prm VARCHAR(50)')
            print("Colonne 'prm' ajoutée à consumer_blocks")

        if 'tarif_type' not in consumer_columns:
            db.engine.execute('ALTER TABLE consumer_blocks ADD COLUMN tarif_type VARCHAR(10) DEFAULT "normal"')
            print("Colonne 'tarif_type' ajoutée à consumer_blocks")

        if 'tarif_normal' not in consumer_columns:
            db.engine.execute('ALTER TABLE consumer_blocks ADD COLUMN tarif_normal FLOAT DEFAULT 0.0')
            print("Colonne 'tarif_normal' ajoutée à consumer_blocks")

        if 'tarif_hc' not in consumer_columns:
            db.engine.execute('ALTER TABLE consumer_blocks ADD COLUMN tarif_hc FLOAT DEFAULT 0.0')
            print("Colonne 'tarif_hc' ajoutée à consumer_blocks")

        if 'tarif_hp' not in consumer_columns:
            db.engine.execute('ALTER TABLE consumer_blocks ADD COLUMN tarif_hp FLOAT DEFAULT 0.0')
            print("Colonne 'tarif_hp' ajoutée à consumer_blocks")

        producer_columns = [col['name'] for col in inspector.get_columns('producer_blocks')]

        # Ajouter les colonnes manquantes
        if 'prm' not in producer_columns:
            db.engine.execute('ALTER TABLE producer_blocks ADD COLUMN prm VARCHAR(50)')
            print("Colonne 'prm' ajoutée à producer_blocks")

    except Exception as e:
        print(f"Migration des colonnes: {e}")

@app.route('/privacy')
def privacy_policy():
    return render_template('privacy_policy.html')

# Routes d'authentification
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('projects'))

    form = LoginForm()

    # Générer un nouveau CAPTCHA
    if request.method == 'GET':
        captcha_question, captcha_answer = CaptchaHelper.generate_captcha()
        session['captcha_answer'] = captcha_answer
        session['captcha_question'] = captcha_question

    if form.validate_on_submit():
        # Vérifier le CAPTCHA
        if form.captcha_answer.data != session.get('captcha_answer'):
            flash('Réponse CAPTCHA incorrecte. Veuillez réessayer.', 'error')
            # Générer un nouveau CAPTCHA
            captcha_question, captcha_answer = CaptchaHelper.generate_captcha()
            session['captcha_answer'] = captcha_answer
            session['captcha_question'] = captcha_question
            return render_template('login.html', form=form, captcha_question=session.get('captcha_question'))

        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            flash(f'Bienvenue {user.username} !', 'success')
            return redirect(next_page) if next_page else redirect(url_for('projects'))
        else:
            flash('Nom d\'utilisateur ou mot de passe incorrect.', 'error')
            # Générer un nouveau CAPTCHA après échec
            captcha_question, captcha_answer = CaptchaHelper.generate_captcha()
            session['captcha_answer'] = captcha_answer
            session['captcha_question'] = captcha_question

    return render_template('login.html', form=form, captcha_question=session.get('captcha_question'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('projects'))

    form = RegistrationForm()

    # Générer un nouveau CAPTCHA
    if request.method == 'GET':
        captcha_question, captcha_answer = CaptchaHelper.generate_captcha()
        session['captcha_answer'] = captcha_answer
        session['captcha_question'] = captcha_question

    if form.validate_on_submit():
        # Vérifier le CAPTCHA
        if form.captcha_answer.data != session.get('captcha_answer'):
            flash('Réponse CAPTCHA incorrecte. Veuillez réessayer.', 'error')
            # Générer un nouveau CAPTCHA
            captcha_question, captcha_answer = CaptchaHelper.generate_captcha()
            session['captcha_answer'] = captcha_answer
            session['captcha_question'] = captcha_question
            return render_template('register.html', form=form, captcha_question=session.get('captcha_question'))

        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash('Inscription réussie ! Vous pouvez maintenant vous connecter.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form, captcha_question=session.get('captcha_question'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Vous avez été déconnecté avec succès.', 'success')
    return redirect(url_for('login'))


# Route principale - redirige vers les projets si connecté
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('projects'))
    return redirect(url_for('login'))


# Routes pour le mode démo
@app.route('/demo')
def demo_mode():
    """Mode démo sans authentification avec support complet"""
    # Créer un identifiant unique pour cette session démo
    demo_session_id = str(uuid.uuid4())

    # Initialiser la session démo
    DEMO_SESSIONS[demo_session_id] = {
        'id': DEMO_PROJECT_ID,
        'session_id': demo_session_id,
        'name': 'Projet Démonstration',
        'description': 'Testez toutes les fonctionnalités de RepartKey',
        'consumer_blocks': [],
        'producer_blocks': [],
        'created_at': datetime.utcnow().isoformat()
    }

    # Créer les dossiers temporaires pour cette session
    demo_upload_folder = os.path.join(UPLOAD_FOLDER, f'demo_{demo_session_id}')
    demo_export_folder = os.path.join(EXPORT_FOLDER, f'demo_{demo_session_id}')
    os.makedirs(demo_upload_folder, exist_ok=True)
    os.makedirs(demo_export_folder, exist_ok=True)

    # Stocker l'ID de session dans un cookie
    response = make_response(render_template('index.html',
                                             project=type('Project', (), {
                                                 'id': DEMO_PROJECT_ID,
                                                 'name': 'Projet Démonstration',
                                                 'description': 'Testez toutes les fonctionnalités'
                                             })(),
                                             text_blocks=[],
                                             consumer_blocks=[],
                                             producer_blocks=[],
                                             project_id=DEMO_PROJECT_ID,
                                             is_demo=True,
                                             demo_session_id=demo_session_id))

    response.set_cookie('demo_session_id', demo_session_id, max_age=3600)  # Expire après 1 heure
    return response


@app.route('/demo/cleanup', methods=['POST'])
def demo_cleanup():
    """Nettoyer une session démo"""
    demo_session_id = request.cookies.get('demo_session_id')
    if demo_session_id:
        cleanup_demo_session(demo_session_id)
    return jsonify({'success': True, 'message': 'Session démo nettoyée'})


@app.route('/demo/add_consumer', methods=['POST'])
def demo_add_consumer():
    """Ajouter un consommateur en mode démo"""
    demo_session_id = request.cookies.get('demo_session_id')
    if not demo_session_id or demo_session_id not in DEMO_SESSIONS:
        return jsonify({'success': False, 'message': 'Session démo expirée'})

    cons_name = request.form.get('cons_name')
    consumer_id = random.randint(1000, 9999)

    # Créer un objet Consumer temporaire
    producer_count = len(DEMO_SESSIONS[demo_session_id]['producer_blocks'])
    priority_list = [0] * producer_count
    ratio_list = [100] * producer_count

    consumer = Consumer.Consumer(cons_name, cons_name, priority_list, ratio_list)

    # Stocker dans la session
    DEMO_SESSIONS[demo_session_id]['consumer_blocks'].append({
        'id': consumer_id,
        'cons_name': cons_name,
        'consumer_object': consumer,
        'priority_list': priority_list,
        'ratio_list': ratio_list,
        'file_path': None
    })

    return jsonify({
        'success': True,
        'message': 'Consommateur ajouté (mode démo)',
        'consumer_id': consumer_id
    })


@app.route('/demo/add_producer', methods=['POST'])
def demo_add_producer():
    """Ajouter un producteur en mode démo"""
    demo_session_id = request.cookies.get('demo_session_id')
    if not demo_session_id or demo_session_id not in DEMO_SESSIONS:
        return jsonify({'success': False, 'message': 'Session démo expirée'})

    prod_name = request.form.get('prod_name')
    producer_id = random.randint(1000, 9999)

    # Créer un objet Producer temporaire
    producer = Producer.Producer(prod_name, 1234567901000)

    # Stocker dans la session
    DEMO_SESSIONS[demo_session_id]['producer_blocks'].append({
        'id': producer_id,
        'prod_name': prod_name,
        'producer_object': producer,
        'file_path': None
    })

    # Mettre à jour tous les consommateurs existants
    for consumer_data in DEMO_SESSIONS[demo_session_id]['consumer_blocks']:
        consumer_data['priority_list'].append(0)
        consumer_data['ratio_list'].append(100)
        if consumer_data['consumer_object']:
            consumer_data['consumer_object'].add_producer_values()

    return jsonify({
        'success': True,
        'message': 'Producteur ajouté (mode démo)',
        'producer_id': producer_id
    })


@app.route('/demo/upload_consumer_file', methods=['POST'])
def demo_upload_consumer_file():
    """Upload de fichier consommateur en mode démo"""
    demo_session_id = request.cookies.get('demo_session_id')
    if not demo_session_id or demo_session_id not in DEMO_SESSIONS:
        return jsonify({'success': False, 'message': 'Session démo expirée'})

    try:
        consumer_id = int(request.form.get('id'))

        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'Aucun fichier sélectionné'})

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Aucun fichier sélectionné'})

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            # Sauvegarder dans le dossier temporaire de la session
            demo_folder = os.path.join(UPLOAD_FOLDER, f'demo_{demo_session_id}')
            filepath = os.path.join(demo_folder, f'consumer_{consumer_id}_{filename}')
            file.save(filepath)

            # Trouver le consommateur dans la session
            for consumer_data in DEMO_SESSIONS[demo_session_id]['consumer_blocks']:
                if consumer_data['id'] == consumer_id:
                    consumer_data['file_path'] = filepath
                    if consumer_data['consumer_object']:
                        consumer_data['consumer_object'].read_consumption(filepath)
                    break

            return jsonify({'success': True, 'message': 'Fichier uploadé', 'filename': filename})
        else:
            return jsonify({'success': False, 'message': 'Type de fichier non autorisé'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})


@app.route('/demo/upload_producer_file', methods=['POST'])
def demo_upload_producer_file():
    """Upload de fichier producteur en mode démo"""
    demo_session_id = request.cookies.get('demo_session_id')
    if not demo_session_id or demo_session_id not in DEMO_SESSIONS:
        return jsonify({'success': False, 'message': 'Session démo expirée'})

    try:
        producer_id = int(request.form.get('id'))

        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'Aucun fichier sélectionné'})

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Aucun fichier sélectionné'})

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            # Sauvegarder dans le dossier temporaire de la session
            demo_folder = os.path.join(UPLOAD_FOLDER, f'demo_{demo_session_id}')
            filepath = os.path.join(demo_folder, f'producer_{producer_id}_{filename}')
            file.save(filepath)

            # Trouver le producteur dans la session
            for producer_data in DEMO_SESSIONS[demo_session_id]['producer_blocks']:
                if producer_data['id'] == producer_id:
                    producer_data['file_path'] = filepath
                    if producer_data['producer_object']:
                        producer_data['producer_object'].read_production(filepath)
                    break

            return jsonify({'success': True, 'message': 'Fichier uploadé', 'filename': filename})
        else:
            return jsonify({'success': False, 'message': 'Type de fichier non autorisé'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})


@app.route('/demo/delete_consumer/<int:consumer_id>', methods=['DELETE'])
def demo_delete_consumer(consumer_id):
    """Supprimer un consommateur en mode démo"""
    demo_session_id = request.cookies.get('demo_session_id')
    if not demo_session_id or demo_session_id not in DEMO_SESSIONS:
        return jsonify({'success': False, 'message': 'Session démo expirée'})

    DEMO_SESSIONS[demo_session_id]['consumer_blocks'] = [
        c for c in DEMO_SESSIONS[demo_session_id].get('consumer_blocks', [])
        if c['id'] != consumer_id
    ]

    return jsonify({'success': True, 'message': 'Consommateur supprimé (mode démo)'})


@app.route('/demo/delete_producer/<int:producer_id>', methods=['DELETE'])
def demo_delete_producer(producer_id):
    """Supprimer un producteur en mode démo"""
    demo_session_id = request.cookies.get('demo_session_id')
    if not demo_session_id or demo_session_id not in DEMO_SESSIONS:
        return jsonify({'success': False, 'message': 'Session démo expirée'})

    # Trouver l'index du producteur à supprimer
    producer_index = -1
    for i, p in enumerate(DEMO_SESSIONS[demo_session_id].get('producer_blocks', [])):
        if p['id'] == producer_id:
            producer_index = i
            break

    # Supprimer le producteur
    DEMO_SESSIONS[demo_session_id]['producer_blocks'] = [
        p for p in DEMO_SESSIONS[demo_session_id].get('producer_blocks', [])
        if p['id'] != producer_id
    ]

    # Mettre à jour tous les consommateurs
    if producer_index >= 0:
        for consumer_data in DEMO_SESSIONS[demo_session_id]['consumer_blocks']:
            if producer_index < len(consumer_data['priority_list']):
                consumer_data['priority_list'].pop(producer_index)
            if producer_index < len(consumer_data['ratio_list']):
                consumer_data['ratio_list'].pop(producer_index)

            if consumer_data['consumer_object']:
                consumer = consumer_data['consumer_object']
                if producer_index < len(consumer.priority_list):
                    consumer.priority_list.pop(producer_index)
                if producer_index < len(consumer.ratio_list):
                    consumer.ratio_list.pop(producer_index)

    return jsonify({'success': True, 'message': 'Producteur supprimé (mode démo)'})


@app.route('/demo/compute_repartition_keys', methods=['POST'])
def demo_compute_repartition_keys():
    """Calculer les clés de répartition en mode démo"""
    demo_session_id = request.cookies.get('demo_session_id')
    if not demo_session_id or demo_session_id not in DEMO_SESSIONS:
        return jsonify({'success': False, 'message': 'Session démo expirée'})

    try:
        key_type = request.form.get('cles', 'default')

        strategy_mapping = {
            'default': Repartition.Strategy.DYNAMIC_BY_DEFAULT,
            'dynamic': Repartition.Strategy.DYNAMIC,
            'static': Repartition.Strategy.STATIC
        }

        strategy = strategy_mapping.get(key_type, Repartition.Strategy.DYNAMIC_BY_DEFAULT)

        # Récupérer les listes depuis la session
        demo_data = DEMO_SESSIONS[demo_session_id]
        prod_list = [p['producer_object'] for p in demo_data['producer_blocks'] if p['producer_object']]
        cons_list = [c['consumer_object'] for c in demo_data['consumer_blocks'] if c['consumer_object']]

        if not prod_list:
            return jsonify({'success': False, 'message': 'Aucun producteur avec fichier ajouté'})

        if not cons_list:
            return jsonify({'success': False, 'message': 'Aucun consommateur avec fichier ajouté'})

        # Vérifier que les fichiers ont été uploadés
        has_prod_files = any(p['file_path'] for p in demo_data['producer_blocks'])
        has_cons_files = any(c['file_path'] for c in demo_data['consumer_blocks'])

        if not has_prod_files or not has_cons_files:
            return jsonify({'success': False,
                            'message': 'Veuillez uploader les fichiers CSV pour tous les producteurs et consommateurs'})

        # Créer le dossier d'export pour cette session
        export_folder = os.path.join(EXPORT_FOLDER, f'demo_{demo_session_id}')

        rep = Repartition.Repartition()
        rep.build_rep(prod_list, cons_list, strategy)
        rep.write_repartition_key(prod_list, cons_list, export_folder, True)

        stat_file_list = rep.generate_statistics(prod_list, cons_list, export_folder)
        rep.generate_monthly_report(prod_list, cons_list, export_folder, add_cons_mois=False)

        # Stocker les résultats dans la session
        demo_data['stat_file_list'] = stat_file_list
        demo_data['stat_file_generated'] = True
        demo_data['auto_consumption_rate_global'] = rep.get_auto_consumption_rate()
        demo_data['auto_production_rate_global'] = rep.get_auto_production_rate()
        demo_data['coverage_rate'] = rep.get_coverage_rate()

        return jsonify({
            'success': True,
            'message': f'Calcul terminé (mode démo)',
            'indicators': {
                'auto_consumption_rate_global': round(demo_data['auto_consumption_rate_global'], 2),
                'auto_production_rate_global': round(demo_data['auto_production_rate_global'], 2),
                'coverage_rate': round(demo_data['coverage_rate'], 2)
            }
        })

    except Exception as e:
        print(f"Erreur lors du calcul démo : {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})


@app.route('/demo/data')
def demo_chart_data():
    """Données du graphique pour le mode démo"""
    demo_session_id = request.cookies.get('demo_session_id')
    if not demo_session_id or demo_session_id not in DEMO_SESSIONS:
        return jsonify({'error': 'Session expirée'}), 404

    demo_data = DEMO_SESSIONS[demo_session_id]
    res = "jour"

    try:
        if demo_data.get('stat_file_generated') and 'stat_file_list' in demo_data and demo_data['stat_file_list']:
            stat_file = demo_data['stat_file_list'][0]

            if os.path.exists(stat_file):
                fig = Graph.generate_graph(stat_file, ';', group=False, resolution=res)

                traces = []
                for trace in fig.data:
                    trace_data = {
                        'type': 'scatter',
                        'mode': 'lines',
                        'fill': 'tonexty' if len(traces) > 0 else 'tozeroy',
                        'stackgroup': 'one',
                        'name': trace.name,
                        'x': [str(x) for x in trace.x],
                        'y': [float(str(y)) if str(y) != 'nan' else 0 for y in trace.y]
                    }
                    traces.append(trace_data)

                return jsonify({
                    'data': traces,
                    'layout': {
                        'title': 'Autoconsommation (Mode Démo)',
                        'xaxis': {'title': 'Date'},
                        'yaxis': {'title': 'Autoconsommation (Wh)'},
                        'legend': {
                            'orientation': 'h',
                            'x': 0.5,
                            'xanchor': 'center',
                            'y': -0.2,
                            'yanchor': 'top'
                        }
                    },
                    'indicators': {
                        'auto_consumption_rate_global': round(demo_data.get('auto_consumption_rate_global', 0), 2),
                        'auto_production_rate_global': round(demo_data.get('auto_production_rate_global', 0), 2),
                        'coverage_rate': round(demo_data.get('coverage_rate', 0), 2)
                    }
                })

        return jsonify({
            'data': [],
            'layout': {
                'title': 'Aucune donnée disponible - Veuillez calculer les clés de répartition',
                'xaxis': {'title': 'Date'},
                'yaxis': {'title': 'Autoconsommation (Wh)'},
                'annotations': [{
                    'x': 0.5, 'y': 0.5,
                    'xref': 'paper', 'yref': 'paper',
                    'text': 'Veuillez calculer les clés de répartition',
                    'showarrow': False,
                    'font': {'size': 16, 'color': '#666'},
                    'xanchor': 'center', 'yanchor': 'middle'
                }]
            },
            'indicators': {
                'auto_consumption_rate_global': 0,
                'auto_production_rate_global': 0,
                'coverage_rate': 0
            }
        })

    except Exception as e:
        print(f"Erreur graphique démo: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# Nettoyer automatiquement les sessions démo expirées (à appeler périodiquement)
@app.before_request
def cleanup_old_demo_sessions():
    """Nettoyer les vieilles sessions démo (plus d'1 heure)"""
    import time
    current_time = time.time()
    sessions_to_remove = []

    for session_id, data in DEMO_SESSIONS.items():
        created_at = datetime.fromisoformat(data['created_at'])
        age_seconds = (datetime.utcnow() - created_at).total_seconds()
        if age_seconds > 3600:  # Plus d'1 heure
            sessions_to_remove.append(session_id)

    for session_id in sessions_to_remove:
        cleanup_demo_session(session_id)


# Route des projets
@app.route('/projects')
@login_required
def projects():
    user_projects = current_user.projects.order_by(Project.date_created.desc()).all()
    form = ProjectForm()
    return render_template('projects.html', projects=user_projects, form=form)


@app.route('/create_project', methods=['POST'])
@login_required
def create_project():
    form = ProjectForm()

    # Vérifier la limite de projets (10 max)
    user_projects_count = current_user.projects.count()
    if user_projects_count >= 10:
        flash(
            'Vous avez atteint la limite de 10 projets. Veuillez supprimer un projet existant pour en créer un nouveau.',
            'error')
        return redirect(url_for('projects'))

    if form.validate_on_submit():
        project = Project(
            name=form.name.data,
            description=form.description.data,
            user_id=current_user.id
        )
        db.session.add(project)
        db.session.commit()

        flash(f'Projet "{project.name}" créé avec succès !', 'success')
        return redirect(url_for('project_dashboard', project_id=project.id))

    flash('Erreur lors de la création du projet.', 'error')
    return redirect(url_for('projects'))


@app.route('/delete_project/<int:project_id>')
@login_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)

    # Vérifier que l'utilisateur est propriétaire du projet
    if project.user_id != current_user.id:
        flash('Vous n\'avez pas l\'autorisation de supprimer ce projet.', 'error')
        return redirect(url_for('projects'))

    # Supprimer les fichiers associés au projet
    for consumer_block in project.consumer_blocks:
        if consumer_block.consumer_object and consumer_block.consumer_object.file_path:
            try:
                os.remove(consumer_block.consumer_object.file_path)
            except:
                pass

    for producer_block in project.producer_blocks:
        if producer_block.producer_object and producer_block.producer_object.file_path:
            try:
                os.remove(producer_block.producer_object.file_path)
            except:
                pass

    # Supprimer les statistiques du projet si elles existent
    if project_id in project_stats:
        del project_stats[project_id]

    db.session.delete(project)
    db.session.commit()

    flash(f'Projet "{project.name}" supprimé avec succès.', 'success')
    return redirect(url_for('projects'))

@app.route('/update-project/<int:project_id>', methods=['POST'])
@login_required
def update_project(project_id):
    project = Project.query.get_or_404(project_id)

    # Vérifier que l'utilisateur est propriétaire du projet
    if project.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Vous n\'avez pas l\'autorisation de modifier ce projet.'}), 403

    data = request.get_json()
    field = data.get('field')
    value = data.get('value')

    if not field or value is None:
        return jsonify({'success': False, 'message': 'Données manquantes'}), 400

    if field == 'name':
        project.name = value
    elif field == 'description':
        project.description = value
    else:
        return jsonify({'success': False, 'message': 'Champ invalide'}), 400

    db.session.commit()
    return jsonify({'success': True})

@app.route('/project/<int:project_id>')
@login_required
def project_dashboard(project_id):
    project = Project.query.get_or_404(project_id)

    # Vérifier que l'utilisateur est propriétaire du projet
    if project.user_id != current_user.id:
        flash('Vous n\'avez pas l\'autorisation d\'accéder à ce projet.', 'error')
        return redirect(url_for('projects'))

    # Récupérer les données du projet
    text_blocks = project.text_blocks.order_by(TextBlock.date_created.desc()).all()
    consumer_blocks = project.consumer_blocks.order_by(ConsumerBlock.id).all()
    producer_blocks = project.producer_blocks.order_by(ProducerBlock.id).all()

    # Passer le project_id au template pour l'utiliser dans les requêtes AJAX
    return render_template('index.html',
                           project=project,
                           text_blocks=text_blocks,
                           consumer_blocks=consumer_blocks,
                           producer_blocks=producer_blocks,
                           project_id=project_id)


# Fonctions utilitaires adaptées pour les projets
def get_cons_list(project_id):
    """Retourne la liste des objets Consumer pour un projet spécifique"""
    project = db.session.get(Project,project_id)
    if not project:
        return []

    consumers = []
    for consumer_block in project.consumer_blocks:
        if consumer_block.consumer_object:
            consumer = consumer_block.consumer_object.get_consumer_object()
            if consumer:
                consumers.append(consumer)
    return consumers


def get_prod_list(project_id):
    """Retourne la liste des objets Producer pour un projet spécifique"""
    project = db.session.get(Project,project_id)
    if not project:
        return []

    producers = []
    for producer_block in project.producer_blocks:
        if producer_block.producer_object:
            producer = producer_block.producer_object.get_producer_object()
            if producer:
                producers.append(producer)
    return producers


def get_producer_count(project_id):
    """Retourne le nombre de producteurs pour un projet spécifique"""
    project = db.session.get(Project,project_id)
    if not project:
        return 0
    return project.producer_blocks.count()


def update_all_consumers_for_new_producer(project_id):
    """Met à jour tous les consumers d'un projet quand un nouveau producteur est ajouté"""
    project = db.session.get(Project,project_id)
    if not project:
        return

    for consumer_block in project.consumer_blocks:
        if consumer_block.consumer_object:
            consumer = consumer_block.consumer_object.get_consumer_object()
            if consumer:
                consumer.add_producer_values()
                consumer_block.consumer_object.set_consumer_object(consumer)
                consumer_block.consumer_object.priority_list = json.dumps(consumer.priority_list)
                consumer_block.consumer_object.ratio_list = json.dumps(consumer.ratio_list)

    db.session.commit()


def update_all_consumers_for_deleted_producer(project_id, producer_index):
    """Met à jour tous les consumers d'un projet quand un producteur est supprimé"""
    project = db.session.get(Project,project_id)
    if not project:
        return

    for consumer_block in project.consumer_blocks:
        if consumer_block.consumer_object:
            consumer = consumer_block.consumer_object.get_consumer_object()
            if consumer:
                if producer_index < len(consumer.priority_list):
                    consumer.priority_list.pop(producer_index)
                if producer_index < len(consumer.ratio_list):
                    consumer.ratio_list.pop(producer_index)

                consumer_block.consumer_object.set_consumer_object(consumer)
                consumer_block.consumer_object.priority_list = json.dumps(consumer.priority_list)
                consumer_block.consumer_object.ratio_list = json.dumps(consumer.ratio_list)

    db.session.commit()


# Routes adaptées pour les projets avec support AJAX
@app.route('/project/<int:project_id>/add_consumer', methods=['POST'])
@login_required
def add_consumer_block(project_id):
    project = Project.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Non autorisé'})

    cons_name = request.form['cons_name']
    # cons_prm = request.form['cons_prm']

    new_consumer_block = ConsumerBlock(cons_name=cons_name, project_id=project_id)

    try:
        db.session.add(new_consumer_block)
        db.session.commit()

        producer_count = get_producer_count(project_id)
        priority_list = [0] * producer_count
        ratio_list = [100] * producer_count

        consumer = Consumer.Consumer(cons_name, cons_name, priority_list, ratio_list)

        # Créer l'objet ConsumerObject
        consumer_obj = ConsumerObject(
            consumer_block_id=new_consumer_block.id,
            consumer_name=cons_name,
            file_path="",
            priority_list=json.dumps(priority_list),
            ratio_list=json.dumps(ratio_list)
        )
        consumer_obj.set_consumer_object(consumer)
        db.session.add(consumer_obj)
        db.session.commit()

        # Retourner l'ID du nouveau consommateur pour la mise à jour dynamique
        return jsonify({
            'success': True,
            'message': 'Consommateur ajouté avec succès',
            'consumer_id': new_consumer_block.id
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})


@app.route('/project/<int:project_id>/add_producer', methods=['POST'])
@login_required
def add_producer_block(project_id):
    project = Project.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Non autorisé'})

    prod_name = request.form['prod_name']
    # prod_prm = request.form['prod_prm']

    new_producer_block = ProducerBlock(prod_name=prod_name, project_id=project_id)

    try:
        db.session.add(new_producer_block)
        db.session.commit()

        producer = Producer.Producer(prod_name, prod_name)

        # Créer l'objet ProducerObject
        producer_obj = ProducerObject(
            producer_block_id=new_producer_block.id,
            producer_name=prod_name,
            file_path=""
        )
        producer_obj.set_producer_object(producer)
        db.session.add(producer_obj)
        db.session.commit()

        update_all_consumers_for_new_producer(project_id)

        # Retourner l'ID du nouveau producteur pour la mise à jour dynamique
        return jsonify({
            'success': True,
            'message': 'Producteur ajouté avec succès',
            'producer_id': new_producer_block.id
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})


# Routes de suppression avec support AJAX
@app.route('/project/<int:project_id>/delete_consumer/<int:consumer_id>', methods=['DELETE', 'GET'])
@login_required
def delete_consumer(project_id, consumer_id):
    project = Project.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        if request.method == 'DELETE':
            return jsonify({'success': False, 'message': 'Non autorisé'})
        else:
            flash('Non autorisé', 'error')
            return redirect(url_for('project_dashboard', project_id=project_id))

    consumer_block = ConsumerBlock.query.get_or_404(consumer_id)

    if consumer_block.project_id != project_id:
        if request.method == 'DELETE':
            return jsonify({'success': False, 'message': 'Non autorisé'})
        else:
            flash('Non autorisé', 'error')
            return redirect(url_for('project_dashboard', project_id=project_id))

    try:
        db.session.delete(consumer_block)
        db.session.commit()

        if request.method == 'DELETE':
            return jsonify({'success': True, 'message': 'Consommateur supprimé avec succès'})
        else:
            flash('Consommateur supprimé avec succès', 'success')
            return redirect(url_for('project_dashboard', project_id=project_id))
    except Exception as e:
        if request.method == 'DELETE':
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})
        else:
            flash(f'Erreur lors de la suppression: {str(e)}', 'error')
            return redirect(url_for('project_dashboard', project_id=project_id))


@app.route('/project/<int:project_id>/delete_producer/<int:producer_id>', methods=['DELETE', 'GET'])
@login_required
def delete_producer(project_id, producer_id):
    project = Project.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        if request.method == 'DELETE':
            return jsonify({'success': False, 'message': 'Non autorisé'})
        else:
            flash('Non autorisé', 'error')
            return redirect(url_for('project_dashboard', project_id=project_id))

    producer_block = ProducerBlock.query.get_or_404(producer_id)

    if producer_block.project_id != project_id:
        if request.method == 'DELETE':
            return jsonify({'success': False, 'message': 'Non autorisé'})
        else:
            flash('Non autorisé', 'error')
            return redirect(url_for('project_dashboard', project_id=project_id))

    try:
        # Obtenir l'index du producteur avant de le supprimer
        producer_index = -1
        all_producers = project.producer_blocks.order_by(ProducerBlock.id).all()
        for idx, prod in enumerate(all_producers):
            if prod.id == producer_id:
                producer_index = idx
                break

        db.session.delete(producer_block)
        db.session.commit()

        # Mettre à jour tous les consumers
        if producer_index >= 0:
            update_all_consumers_for_deleted_producer(project_id, producer_index)

        if request.method == 'DELETE':
            return jsonify({'success': True, 'message': 'Producteur supprimé avec succès'})
        else:
            flash('Producteur supprimé avec succès', 'success')
            return redirect(url_for('project_dashboard', project_id=project_id))
    except Exception as e:
        if request.method == 'DELETE':
            return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})
        else:
            flash(f'Erreur lors de la suppression: {str(e)}', 'error')
            return redirect(url_for('project_dashboard', project_id=project_id))


@app.route('/project/<int:project_id>/compute_repartition_keys', methods=['POST'])
@login_required
def compute_repartition_keys(project_id):
    project = Project.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Non autorisé'})

    try:
        key_type = request.form.get('cles', 'default')

        strategy_mapping = {
            'default': Repartition.Strategy.DYNAMIC_BY_DEFAULT,
            'dynamic': Repartition.Strategy.DYNAMIC,
            'static': Repartition.Strategy.STATIC
        }

        strategy = strategy_mapping.get(key_type, Repartition.Strategy.DYNAMIC_BY_DEFAULT)

        prod_list = get_prod_list(project_id)
        cons_list = get_cons_list(project_id)

        if not prod_list:
            return jsonify({'success': False, 'message': 'Aucun producteur ajouté'})

        if not cons_list:
            return jsonify({'success': False, 'message': 'Aucun consommateur ajouté'})

        # Créer des dossiers spécifiques au projet
        project_export_folder = os.path.join(EXPORT_FOLDER, f'project_{project_id}')
        if not os.path.exists(project_export_folder):
            os.makedirs(project_export_folder, exist_ok=True)

        rep = Repartition.Repartition()
        rep.build_rep(prod_list, cons_list, strategy)
        rep.write_repartition_key(prod_list, cons_list, project_export_folder, False)

        stat_file_list = rep.generate_statistics(prod_list, cons_list, project_export_folder)
        rep.generate_monthly_report(prod_list, cons_list, project_export_folder, add_cons_mois=False)

        # Stocker les statistiques par projet
        if project_id not in project_stats:
            project_stats[project_id] = {}

        project_stats[project_id]['stat_file_list'] = stat_file_list
        project_stats[project_id]['stat_file_generated'] = True
        project_stats[project_id]['auto_consumption_rate_global'] = rep.get_auto_consumption_rate()
        project_stats[project_id]['auto_production_rate_global'] = rep.get_auto_production_rate()
        project_stats[project_id]['coverage_rate'] = rep.get_coverage_rate()

        auto_consumption_rate = []
        auto_consumption_rate_detailed = []
        for prod_index, producer in enumerate(prod_list):
            auto_consumption_rate.append(rep.get_auto_consumption_rate(index_producer=prod_index))
            auto_consumption_rate_detailed.append([])
            for cons_index, consumer in enumerate(cons_list):
                auto_consumption_rate_detailed[prod_index].append(rep.get_auto_consumption_rate(index_producer=prod_index, index_consumer=cons_index))
        project_stats[project_id]['auto_consumption_rate'] = auto_consumption_rate
        project_stats[project_id]['auto_consumption_rate_detailed'] = auto_consumption_rate_detailed

        auto_production_rate = []
        auto_production_rate_detailed = []
        for cons_index, consumer in enumerate(cons_list):
            auto_production_rate.append(rep.get_auto_production_rate(index_consumer=cons_index))
            auto_production_rate_detailed.append([])
            for prod_index, producer in enumerate(prod_list):
                auto_production_rate_detailed[cons_index].append(rep.get_auto_production_rate(index_consumer=cons_index, index_producer=prod_index))
        project_stats[project_id]['auto_production_rate'] = auto_production_rate
        project_stats[project_id]['auto_production_rate_detailed'] = auto_production_rate_detailed

        return jsonify({
                'success': True,
                'message': f'Calcul des clés de répartition terminé avec succès (Stratégie: {key_type})',
                'indicators': {
                    'auto_consumption_rate_global': round(project_stats[project_id]['auto_consumption_rate_global'], 2),
                    'auto_production_rate_global': round(project_stats[project_id]['auto_production_rate_global'], 2),
                    'coverage_rate': round(project_stats[project_id]['coverage_rate'], 2)
                }
            })

    except Exception as e:
        print(f"Erreur lors du calcul : {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Erreur lors du calcul : {str(e)}'})


@app.route('/project/<int:project_id>/data')
@login_required
def chart_data(project_id):
    project = Project.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return jsonify({'error': 'Non autorisé'}), 403

    # Resolution value (mois, jour, heure)
    res = "heure"
    # Trace type (bar, scatter)
    trace_type = "bar"

    try:
        if project_id in project_stats and project_stats[project_id].get('stat_file_generated'):
            stat_file_list = project_stats[project_id]['stat_file_list']

            if stat_file_list and len(stat_file_list) > 0:
                if not os.path.exists(stat_file_list[0]):
                    raise FileNotFoundError(f"Le fichier de statistiques {stat_file_list[0]} n'existe pas")

                fig = Graph.generate_graph(stat_file_list[0], ';', group=False, resolution=res)

                if not hasattr(fig, 'data') or len(fig.data) == 0:
                    raise ValueError("Le graphique généré ne contient aucune donnée")

                fig.update_layout(
                    autosize=True,
                    margin=dict(autoexpand=True)
                )

                traces = []

                if trace_type == 'bar':
                    for trace in fig.data:
                        trace_data = {
                            'type': 'bar',  # Changé de 'scatter' à 'bar'
                            'name': trace.name,
                            'x': [str(x) for x in trace.x],
                            'y': [float(str(y)) if str(y) != 'nan' else 0 for y in trace.y]
                        }
                        traces.append(trace_data)

                    result = {
                        'data': traces,
                        'layout': {
                            'title': 'Autoconsommation cumulée par ' + res,
                            'xaxis': {'title': 'Date'},
                            'yaxis': {'title': 'Autoconsommation (Wh)'},
                            'barmode': 'stack',  # Important : ajouter cette ligne pour empiler les barres
                            'legend': {
                                'orientation': 'h',
                                'x': 0.5,
                                'xanchor': 'center',
                                'y': -0.2,
                                'yanchor': 'top'
                            }
                        },
                        'indicators': {
                            'auto_consumption_rate_global': round(project_stats[project_id]['auto_consumption_rate_global'],
                                                                  2),
                            'auto_production_rate_global': round(project_stats[project_id]['auto_production_rate_global'],
                                                                 2),
                            'coverage_rate': round(project_stats[project_id]['coverage_rate'], 2)
                        }
                    }
                else:
                    for trace in fig.data:
                        trace_data = {
                            'type': 'scatter',
                            'mode': 'lines',
                            'fill': 'tonexty' if len(traces) > 0 else 'tozeroy',
                            'stackgroup': 'one',
                            'name': trace.name,
                            'x': [str(x) for x in trace.x],
                            'y': [float(str(y)) if str(y) != 'nan' else 0 for y in trace.y]
                        }
                        traces.append(trace_data)

                    result = {
                        'data': traces,
                        'layout': {
                            'title': 'Autoconsommation cumulée par ' + res,
                            'xaxis': {'title': 'Date'},
                            'yaxis': {'title': 'Autoconsommation (kWh)'},
                            'legend': {
                                'orientation': 'h',
                                'x': 0.5,
                                'xanchor': 'center',
                                'y': -0.2,
                                'yanchor': 'top'
                            }
                        },
                        'indicators': {
                            'auto_consumption_rate_global': round(
                                project_stats[project_id]['auto_consumption_rate_global'],
                                2),
                            'auto_production_rate_global': round(
                                project_stats[project_id]['auto_production_rate_global'],
                                2),
                            'coverage_rate': round(project_stats[project_id]['coverage_rate'], 2)
                        }
                    }

                return jsonify(result)

        # Retourner un graphique vide par défaut
        result = {
            'data': [],
            'layout': {
                'title': 'Aucune donnée disponible - Veuillez calculer les clés de répartition',
                'xaxis': {'title': 'Date'},
                'yaxis': {'title': 'Autoconsommation (Wh)'},
                'annotations': [{
                    'x': 0.5, 'y': 0.5,
                    'xref': 'paper', 'yref': 'paper',
                    'text': 'Veuillez calculer les clés de répartition',
                    'showarrow': False,
                    'font': {'size': 16, 'color': '#666'},
                    'xanchor': 'center', 'yanchor': 'middle'
                }]
            },
            'indicators': {
                'auto_consumption_rate_global': 0,
                'auto_production_rate_global': 0,
                'coverage_rate': 0
            }
        }
        return jsonify(result)

    except Exception as e:
        print(f"Erreur lors de la génération du graphique : {str(e)}")
        result = {
            'data': [],
            'layout': {
                'title': 'Erreur lors de la génération du graphique',
                'xaxis': {'title': 'Date'},
                'yaxis': {'title': 'Autoconsommation (Wh)'},
                'annotations': [{
                    'x': 0.5, 'y': 0.5,
                    'xref': 'paper', 'yref': 'paper',
                    'text': f'Erreur: {str(e)}',
                    'showarrow': False,
                    'font': {'size': 14, 'color': '#d32f2f'},
                    'xanchor': 'center', 'yanchor': 'middle'
                }]
            },
            'indicators': {
                'auto_consumption_rate_global': 0,
                'auto_production_rate_global': 0,
                'coverage_rate': 0
            }
        }
        return jsonify(result)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Routes pour l'upload de fichiers
@app.route('/project/<int:project_id>/upload_consumer_file', methods=['POST'])
@login_required
def upload_consumer_file(project_id):
    project = Project.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Non autorisé'})

    try:
        cons_name = request.form.get('cons_name')
        consumer_id = request.form.get('id')

        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'Aucun fichier sélectionné'})

        file = request.files['file']

        if file.filename == '':
            return jsonify({'success': False, 'message': 'Aucun fichier sélectionné'})

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            # Créer le dossier du projet si nécessaire
            project_upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], f'project_{project_id}')
            if not os.path.exists(project_upload_folder):
                os.makedirs(project_upload_folder, exist_ok=True)

            filepath = os.path.join(project_upload_folder, filename)
            file.save(filepath)

            if not os.path.exists(filepath):
                return jsonify({'success': False, 'message': 'Le fichier n\'a pas pu être sauvegardé'})

            # Récupérer le ConsumerBlock et son objet
            consumer_block = db.session.get(ConsumerBlock,int(consumer_id))
            if not consumer_block or consumer_block.project_id != project_id:
                return jsonify({'success': False, 'message': 'Consommateur non trouvé'})

            if consumer_block.consumer_object:
                consumer = consumer_block.consumer_object.get_consumer_object()
                if consumer:
                    consumer.read_consumption(filepath)
                    consumer_block.consumer_object.file_path = filepath
                    consumer_block.consumer_object.set_consumer_object(consumer)
                    db.session.commit()
                    return jsonify({'success': True, 'message': 'Fichier uploadé avec succès', 'filename': filename})

            return jsonify({'success': False, 'message': 'Objet consommateur non trouvé'})
        else:
            return jsonify({'success': False, 'message': 'Type de fichier non autorisé'})

    except Exception as e:
        print(f"Erreur dans upload_consumer_file: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Erreur serveur: {str(e)}'})


@app.route('/project/<int:project_id>/upload_producer_file', methods=['POST'])
@login_required
def upload_producer_file(project_id):
    project = Project.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Non autorisé'})

    try:
        prod_name = request.form.get('prod_name')
        producer_id = request.form.get('id')

        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'Aucun fichier sélectionné'})

        file = request.files['file']

        if file.filename == '':
            return jsonify({'success': False, 'message': 'Aucun fichier sélectionné'})

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            # Créer le dossier du projet si nécessaire
            project_upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], f'project_{project_id}')
            if not os.path.exists(project_upload_folder):
                os.makedirs(project_upload_folder, exist_ok=True)

            filepath = os.path.join(project_upload_folder, filename)
            file.save(filepath)

            if not os.path.exists(filepath):
                return jsonify({'success': False, 'message': 'Le fichier n\'a pas pu être sauvegardé'})

            # Récupérer le ProducerBlock et son objet
            producer_block = db.session.get(ProducerBlock,int(producer_id))
            if not producer_block or producer_block.project_id != project_id:
                return jsonify({'success': False, 'message': 'Producteur non trouvé'})

            if producer_block.producer_object:
                producer = producer_block.producer_object.get_producer_object()
                if producer:
                    producer.read_production(filepath)
                    producer_block.producer_object.file_path = filepath
                    producer_block.producer_object.set_producer_object(producer)
                    db.session.commit()
                    return jsonify({'success': True, 'message': 'Fichier uploadé avec succès', 'filename': filename})

            return jsonify({'success': False, 'message': 'Objet producteur non trouvé'})
        else:
            return jsonify({'success': False,
                            'message': f'Type de fichier non autorisé. Types autorisés: {", ".join(ALLOWED_EXTENSIONS)}'})

    except Exception as e:
        print(f"Erreur dans upload_producer_file: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Erreur serveur: {str(e)}'})


# Routes pour la mise à jour des données
@app.route('/project/<int:project_id>/update_consumer_data', methods=['POST'])
@login_required
def update_consumer_data(project_id):
    project = Project.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Non autorisé'})

    try:
        data = request.get_json()
        consumer_id = data.get('consumer_id')
        producer_index = data.get('producer_index')
        field_type = data.get('field_type')
        value = data.get('value')

        consumer_block = ConsumerBlock.query.get_or_404(consumer_id)

        if consumer_block.project_id != project_id:
            return jsonify({'success': False, 'message': 'Non autorisé'})

        if field_type == 'priority':
            consumer_block.set_priority_for_producer(producer_index, value)
        elif field_type == 'ratio':
            consumer_block.set_ratio_for_producer(producer_index, value)

        return jsonify({'success': True, 'message': 'Données mises à jour'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# Routes pour l'édition
@app.route('/project/<int:project_id>/update_consumer/<int:consumer_id>', methods=['GET', 'POST'])
@login_required
def update_consumer(project_id, consumer_id):
    project = Project.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Non autorisé', 'error')
        return redirect(url_for('project_dashboard', project_id=project_id))

    consumer_block = ConsumerBlock.query.get_or_404(consumer_id)

    if consumer_block.project_id != project_id:
        flash('Non autorisé', 'error')
        return redirect(url_for('project_dashboard', project_id=project_id))

    if request.method == 'POST':
        # Récupérer les données du formulaire
        consumer_block.cons_name = request.form['cons_name']
        consumer_block.prm = request.form.get('prm', '').strip() or None
        consumer_block.tarif_type = request.form.get('tarif_type', 'normal')

        # Traitement des tarifs
        try:
            consumer_block.tarif_normal = float(request.form.get('tarif_normal', 0)) or 0.0

            if consumer_block.tarif_type == 'hp_hc':
                consumer_block.tarif_hc = float(request.form.get('tarif_hc', 0)) or 0.0
                consumer_block.tarif_hp = float(request.form.get('tarif_hp', 0)) or 0.0
            else:
                # Réinitialiser les tarifs HP/HC si mode normal
                consumer_block.tarif_hc = 0.0
                consumer_block.tarif_hp = 0.0

        except (ValueError, TypeError):
            flash('Erreur dans les valeurs de tarifs', 'error')
            return render_template('update_consumer.html', consumer_block=consumer_block, project_id=project_id)

        try:
            db.session.commit()
            flash('Consommateur mis à jour avec succès', 'success')
            return redirect(url_for('project_dashboard', project_id=project_id))
        except Exception as e:
            flash(f'Erreur lors de la mise à jour: {str(e)}', 'error')

    return render_template('update_consumer.html', consumer_block=consumer_block, project_id=project_id)


@app.route('/project/<int:project_id>/update_producer/<int:producer_id>', methods=['GET', 'POST'])
@login_required
def update_producer(project_id, producer_id):
    project = Project.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Non autorisé', 'error')
        return redirect(url_for('project_dashboard', project_id=project_id))

    producer_block = ProducerBlock.query.get_or_404(producer_id)

    if producer_block.project_id != project_id:
        flash('Non autorisé', 'error')
        return redirect(url_for('project_dashboard', project_id=project_id))

    if request.method == 'POST':
        producer_block.prod_name = request.form['prod_name']
        producer_block.prm = request.form.get('prm', '').strip() or None

        try:
            db.session.commit()
            flash('Producteur mis à jour avec succès', 'success')
            return redirect(url_for('project_dashboard', project_id=project_id))
        except Exception as e:
            flash(f'Erreur lors de la mise à jour: {str(e)}', 'error')

    return render_template('update_producer.html', producer_block=producer_block, project_id=project_id)

@app.route('/project/<int:project_id>/detailed_indicators', methods=['GET'])
@login_required
def get_detailed_indicators(project_id):
    """
    Retourne les indicateurs détaillés (taux d'autoproduction et d'autoconsommation)
    pour chaque consommateur et producteur d'un projet, en utilisant leurs index.
    """
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        return jsonify({'error': 'Non autorisé'}), 403

    try:
        # Récupérer les objets Producer et Consumer pour ce projet
        prod_list = get_prod_list(project_id)
        cons_list = get_cons_list(project_id)

        if not prod_list or not cons_list:
            return jsonify({
                'success': False,
                'message': 'Aucun producteur ou consommateur trouvé pour ce projet.'
            }), 404

        # Exemple : Calculer les indicateurs (à adapter selon votre logique métier)
        # Ici, on utilise les index des listes prod_list et cons_list
        indicators = []
        for cons_index, consumer in enumerate(cons_list):
            for prod_index, producer in enumerate(prod_list):

                auto_production_rate = project_stats[project_id]['auto_production_rate_detailed'][cons_index][prod_index]
                auto_consumption_rate = project_stats[project_id]['auto_consumption_rate_detailed'][prod_index][cons_index]

                indicators.append({
                    'consumer_id': cons_index,  # Index du consommateur dans cons_list
                    'producer_id': prod_index,   # Index du producteur dans prod_list
                    'auto_production_rate': round(auto_production_rate, 2),
                    'auto_consumption_rate': round(auto_consumption_rate, 2)
                })

        # Calculer les taux globaux
        global_auto_consumption_rates = {str(prod_index): project_stats[project_id]['auto_consumption_rate'][prod_index] for prod_index in range(len(prod_list))}
        global_auto_production_rates = {str(cons_index): project_stats[project_id]['auto_production_rate'][cons_index] for cons_index in range(len(cons_list))}

        return jsonify({
            'success': True,
            'indicators': indicators,
            'global_auto_consumption_rates': global_auto_consumption_rates,
            'global_auto_production_rates': global_auto_production_rates
        })

    except Exception as e:
        print(f"Erreur lors de la récupération des indicateurs détaillés : {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erreur serveur : {str(e)}'
        }), 500

@app.route('/project/<int:project_id>/export_files', methods=['GET'])
@login_required
def list_export_files(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        return jsonify({'error': 'Non autorisé'}), 403

    try:
        # Chemin vers le dossier d'export du projet
        project_export_folder = os.path.join(EXPORT_FOLDER, f'project_{project_id}')

        if not os.path.exists(project_export_folder):
            return jsonify({
                'success': False,
                'message': 'Aucun fichier exporté disponible pour ce projet.'
            })

        # Lister les fichiers dans le dossier d'export
        files = []
        for filename in os.listdir(project_export_folder):
            filepath = os.path.join(project_export_folder, filename)
            if os.path.isfile(filepath):
                files.append({
                    'name': filename,
                    'url': f'/project/{project_id}/download_export_file/{filename}'
                })

        if not files:
            return jsonify({
                'success': False,
                'message': 'Aucun fichier exporté disponible pour ce projet.'
            })

        return jsonify({
            'success': True,
            'files': files
        })

    except Exception as e:
        print(f"Erreur lors de la liste des fichiers exportés: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erreur serveur: {str(e)}'
        }), 500

@app.route('/project/<int:project_id>/download_export_file/<filename>', methods=['GET'])
@login_required
def download_export_file(project_id, filename):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        return jsonify({'error': 'Non autorisé'}), 403

    try:
        # Chemin vers le dossier d'export du projet
        project_export_folder = os.path.join(EXPORT_FOLDER, f'project_{project_id}')

        if not os.path.exists(os.path.join(project_export_folder, filename)):
            return jsonify({'error': 'Fichier non trouvé'}), 404

        return send_from_directory(project_export_folder, filename, as_attachment=True)

    except Exception as e:
        print(f"Erreur lors du téléchargement du fichier: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/project/<int:project_id>/save_repartition_key_type', methods=['POST'])
@login_required
def save_repartition_key_type(project_id):
    project = Project.query.get_or_404(project_id)
    data = request.get_json()

    if 'key_type' not in data:
        return jsonify({'success': False, 'message': 'Type de clé de répartition manquant'}), 400

    key_type = data['key_type']
    project.repartition_key_type = key_type
    db.session.commit()

    return jsonify({'success': True, 'message': 'Type de clé de répartition sauvegardé avec succès'})

@app.route('/project/<int:project_id>/get_repartition_key_type', methods=['GET'])
@login_required
def get_repartition_key_type(project_id):
    project = Project.query.get_or_404(project_id)
    return jsonify({'success': True, 'repartition_key_type': project.repartition_key_type})

@app.route('/project/<int:project_id>/save_priority_settings', methods=['POST'])
@login_required
def save_priority_settings(project_id):
    try:
        # Vérifier que le projet existe et appartient à l'utilisateur
        project = Project.query.get_or_404(project_id)

        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Aucune donnée reçue"}), 400

        # Supprimer les anciennes configurations pour ce projet
        PrioritySettings.query.filter_by(project_id=project_id).delete()

        # Insérer les nouvelles configurations
        for item in data:
            producer = item.get('producer')
            priority = item.get('priority')
            enabled = item.get('enabled')

            if producer is not None and priority is not None and enabled is not None:
                priority_setting = PrioritySettings(
                    project_id=project_id,
                    producer=producer,
                    priority=priority,
                    enabled=enabled
                )
                db.session.add(priority_setting)

        db.session.commit()
        return jsonify({"status": "success", "message": "Paramètres de priorité enregistrés"})

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Erreur lors de la sauvegarde des priorités: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/project/<int:project_id>/get_priority_settings', methods=['GET'])
@login_required
def get_priority_settings(project_id):
    try:
        # Vérifier que le projet existe et appartient à l'utilisateur
        project = Project.query.get_or_404(project_id)

        settings = PrioritySettings.query.filter_by(project_id=project_id).all()
        result = [
            {
                'producer': setting.producer,
                'priority': setting.priority,
                'enabled': setting.enabled
            }
            for setting in settings
        ]
        return jsonify({"status": "success", "data": result})

    except Exception as e:
        app.logger.error(f"Erreur lors de la récupération des priorités: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
