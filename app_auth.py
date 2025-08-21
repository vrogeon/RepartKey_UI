# app_auth.py - Version avec authentification et gestion de projets

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import sys
import json
import pickle

# Import des modèles et formulaires
from models import db, User, Project, TextBlock, ConsumerBlock, ProducerBlock, ConsumerObject, ProducerObject
from forms import LoginForm, RegistrationForm, ProjectForm, CaptchaHelper

# Import des modules métier existants
import Consumer
import Producer
import Repartition
import Graph

import plotly.graph_objects as go
import plotly.utils

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
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), "repartkey.db")}'
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

# Fonction de chargement de l'utilisateur pour Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Créer les tables de la base de données
with app.app_context():
    db.create_all()

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
    
    # Passer le projet_id au template pour l'utiliser dans les requêtes AJAX
    return render_template('index.html', 
                          project=project,
                          text_blocks=text_blocks, 
                          consumer_blocks=consumer_blocks,
                          producer_blocks=producer_blocks,
                          project_id=project_id)

# Fonctions utilitaires adaptées pour les projets
def get_cons_list(project_id):
    """Retourne la liste des objets Consumer pour un projet spécifique"""
    project = Project.query.get(project_id)
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
    project = Project.query.get(project_id)
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
    project = Project.query.get(project_id)
    if not project:
        return 0
    return project.producer_blocks.count()

def update_all_consumers_for_new_producer(project_id):
    """Met à jour tous les consumers d'un projet quand un nouveau producteur est ajouté"""
    project = Project.query.get(project_id)
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
    project = Project.query.get(project_id)
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

# Routes adaptées pour les projets
@app.route('/project/<int:project_id>/add_consumer', methods=['POST'])
@login_required
def add_consumer_block(project_id):
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Non autorisé'})
    
    cons_name = request.form['cons_name']
    
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
        
        return jsonify({'success': True, 'message': 'Consommateur ajouté avec succès'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})

@app.route('/project/<int:project_id>/add_producer', methods=['POST'])
@login_required
def add_producer_block(project_id):
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Non autorisé'})
    
    prod_name = request.form['prod_name']
    
    new_producer_block = ProducerBlock(prod_name=prod_name, project_id=project_id)
    
    try:
        db.session.add(new_producer_block)
        db.session.commit()
        
        producer = Producer.Producer(prod_name, 1234567901000)
        
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
        
        return jsonify({'success': True, 'message': 'Producteur ajouté avec succès'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})

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
        rep.write_repartition_key(prod_list, cons_list, project_export_folder, True)
        
        stat_file_list = rep.generate_statistics(prod_list, cons_list, project_export_folder)
        rep.generate_monthly_report(prod_list, cons_list, project_export_folder, add_cons_mois=False)
        
        # Stocker les statistiques par projet
        if project_id not in project_stats:
            project_stats[project_id] = {}
        
        project_stats[project_id]['stat_file_list'] = stat_file_list
        project_stats[project_id]['stat_file_generated'] = True
        project_stats[project_id]['auto_consumption_rate'] = rep.get_auto_consumption_rate(0)
        project_stats[project_id]['auto_production_rate_global'] = rep.get_global_auto_production_rate(cons_list)
        project_stats[project_id]['coverage_rate'] = rep.get_coverage_rate(0, cons_list)
        
        return jsonify({
            'success': True,
            'message': f'Calcul des clés de répartition terminé avec succès (Stratégie: {key_type})',
            'indicators': {
                'auto_consumption_rate': round(project_stats[project_id]['auto_consumption_rate'], 2),
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
    
    res = "jour"
    
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
                        'auto_consumption_rate': round(project_stats[project_id]['auto_consumption_rate'], 2),
                        'auto_production_rate_global': round(project_stats[project_id]['auto_production_rate_global'], 2),
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
                'yaxis': {'title': 'Autoconsommation (kWh)'}
            },
            'indicators': {
                'auto_consumption_rate': 0,
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
                'yaxis': {'title': 'Autoconsommation (kWh)'}
            },
            'indicators': {
                'auto_consumption_rate': 0,
                'auto_production_rate_global': 0,
                'coverage_rate': 0
            }
        }
        return jsonify(result)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

if __name__ == '__main__':
    app.run(debug=True)