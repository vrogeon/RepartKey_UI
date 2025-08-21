from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import sys
import json
import pickle

import io
import csv

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
    
    # Utiliser os.path.join pour être compatible avec tous les OS
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'Courbes')
    EXPORT_FOLDER = os.path.join(BASE_DIR, 'Export')
    
    # Normaliser les chemins pour éviter les problèmes de séparateurs
    UPLOAD_FOLDER = os.path.normpath(UPLOAD_FOLDER)
    EXPORT_FOLDER = os.path.normpath(EXPORT_FOLDER)
    
    # Créer les dossiers s'ils n'existent pas avec permissions explicites
    try:
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER, mode=0o755, exist_ok=True)
            print(f"Upload folder created at: {UPLOAD_FOLDER}")
        
        if not os.path.exists(EXPORT_FOLDER):
            os.makedirs(EXPORT_FOLDER, mode=0o755, exist_ok=True)
            print(f"Export folder created at: {EXPORT_FOLDER}")
            
        # Vérifier que les dossiers existent vraiment
        if os.path.exists(UPLOAD_FOLDER):
            print(f"✓ Upload folder exists: {UPLOAD_FOLDER}")
        else:
            print(f"✗ Upload folder does not exist: {UPLOAD_FOLDER}")
            
        if os.path.exists(EXPORT_FOLDER):
            print(f"✓ Export folder exists: {EXPORT_FOLDER}")
        else:
            print(f"✗ Export folder does not exist: {EXPORT_FOLDER}")
            
    except Exception as e:
        print(f"Error creating directories: {e}")
        import traceback
        traceback.print_exc()
    
    return UPLOAD_FOLDER, EXPORT_FOLDER

# Initialiser les chemins
UPLOAD_FOLDER, EXPORT_FOLDER = setup_paths()

# Configuration de l'application
app = Flask(__name__)

# Database configuration - utiliser une base de données dans le répertoire de l'app
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), "textblocks.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limite à 16MB

# Ajout d'une clé secrète (nécessaire pour Flask)
app.secret_key = 'your-secret-key-change-this-in-production'  # Changez ceci par une vraie clé secrète

db = SQLAlchemy(app)

# Extensions de fichiers autorisées
ALLOWED_EXTENSIONS = {'csv'}

auto_consumption_rate = 0
auto_production_rate_global = 0
coverage_rate = 0

stat_file_list = []

# Global variables used to manage interactions between different blocs
stat_file_generated = False

# Fonction helper pour gérer les redirections intelligemment
def smart_redirect(endpoint='/'):
    """
    Fonction helper pour gérer les redirections intelligemment
    selon l'environnement (local vs cPanel)
    """
    # Vérifier si on est sur le domaine cPanel
    if request.environ.get('HTTP_HOST', '').startswith('apenco.fr'):
        if endpoint == '/':
            return redirect('/RepartElec/')
        elif endpoint.startswith('/'):
            return redirect('/RepartElec' + endpoint)
        else:
            return redirect('/RepartElec/' + endpoint)
    else:
        # Environnement local
        return redirect(endpoint)

def check_permissions():
    """Vérifie les permissions des dossiers"""
    try:
        # Normaliser les chemins
        upload_path = os.path.normpath(UPLOAD_FOLDER)
        export_path = os.path.normpath(EXPORT_FOLDER)
        
        print(f"Checking permissions for:")
        print(f"  Upload folder: {upload_path}")
        print(f"  Export folder: {export_path}")
        
        # Créer les dossiers s'ils n'existent pas
        if not os.path.exists(upload_path):
            os.makedirs(upload_path, mode=0o755, exist_ok=True)
            print(f"Created upload folder: {upload_path}")
            
        if not os.path.exists(export_path):
            os.makedirs(export_path, mode=0o755, exist_ok=True)
            print(f"Created export folder: {export_path}")
        
        # Test d'écriture dans le dossier upload
        test_file = os.path.join(upload_path, 'test.txt')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print("✓ Upload folder is writable")
        
        # Test d'écriture dans le dossier export
        test_file = os.path.join(export_path, 'test.txt')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print("✓ Export folder is writable")
        
        return True
    except Exception as e:
        print(f"Permission error: {e}")
        import traceback
        traceback.print_exc()
        return False


class TextBlock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TextBlock {self.title}>'


class ConsumerBlock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cons_name = db.Column(db.String(100), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    def get_consumer_object(self):
        """Retourne l'objet Consumer associé"""
        consumer_obj = ConsumerObject.query.filter_by(consumer_block_id=self.id).first()
        if consumer_obj:
            return consumer_obj.get_consumer_object()
        return None

    def get_priority_for_producer(self, producer_index):
        """Retourne la priorité pour un producteur spécifique"""
        consumer = self.get_consumer_object()
        if consumer and producer_index < len(consumer.priority_list):
            return consumer.priority_list[producer_index]
        return 0  # Valeur par défaut

    def get_ratio_for_producer(self, producer_index):
        """Retourne le ratio pour un producteur spécifique"""
        consumer = self.get_consumer_object()
        if consumer and producer_index < len(consumer.ratio_list):
            return consumer.ratio_list[producer_index]
        return 0  # Valeur par défaut

    def set_priority_for_producer(self, producer_index, value):
        """Définit la priorité pour un producteur spécifique"""
        consumer_obj_record = ConsumerObject.query.filter_by(consumer_block_id=self.id).first()
        if consumer_obj_record:
            consumer = consumer_obj_record.get_consumer_object()
            if consumer:
                # Étendre la liste si nécessaire
                while len(consumer.priority_list) <= producer_index:
                    consumer.priority_list.append(0)
                consumer.priority_list[producer_index] = int(value)

                # Sauvegarder l'objet modifié
                consumer_obj_record.set_consumer_object(consumer)
                consumer_obj_record.priority_list = json.dumps(consumer.priority_list)
                db.session.commit()

    def set_ratio_for_producer(self, producer_index, value):
        """Définit le ratio pour un producteur spécifique"""
        consumer_obj_record = ConsumerObject.query.filter_by(consumer_block_id=self.id).first()
        if consumer_obj_record:
            consumer = consumer_obj_record.get_consumer_object()
            if consumer:
                # Étendre la liste si nécessaire
                while len(consumer.ratio_list) <= producer_index:
                    consumer.ratio_list.append(0)
                consumer.ratio_list[producer_index] = int(value)

                # Sauvegarder l'objet modifié
                consumer_obj_record.set_consumer_object(consumer)
                consumer_obj_record.ratio_list = json.dumps(consumer.ratio_list)
                db.session.commit()

    def __repr__(self):
        return f'<ConsumerBlock {self.cons_name}>'
        
    def get_file_name(self):
        """Retourne le nom du fichier associé au consommateur"""
        consumer_obj = ConsumerObject.query.filter_by(consumer_block_id=self.id).first()
        if consumer_obj and consumer_obj.file_path:
            return os.path.basename(consumer_obj.file_path)
        return None
    
    def has_file(self):
        """Vérifie si un fichier est associé au consommateur"""
        return self.get_file_name() is not None


class ProducerBlock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prod_name = db.Column(db.String(100), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ProducerBlock {self.prod_name}>'

    def get_file_name(self):
        """Retourne le nom du fichier associé au producteur"""
        producer_obj = ProducerObject.query.filter_by(producer_block_id=self.id).first()
        if producer_obj and producer_obj.file_path:
            return os.path.basename(producer_obj.file_path)
        return None
    
    def has_file(self):
        """Vérifie si un fichier est associé au producteur"""
        return self.get_file_name() is not None

# Nouveaux modèles SQLAlchemy pour stocker les objets Consumer et Producer
class ConsumerObject(db.Model):
    __tablename__ = 'consumer_objects'

    id = db.Column(db.Integer, primary_key=True)
    consumer_block_id = db.Column(db.Integer, db.ForeignKey('consumer_block.id'), unique=True, nullable=False)
    consumer_name = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    priority_list = db.Column(db.Text, default='[]')  # JSON des priorités
    ratio_list = db.Column(db.Text, default='[]')  # JSON des ratios
    object_data = db.Column(db.LargeBinary, nullable=True)  # Objet sérialisé (pickle)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    # Relation avec ConsumerBlock
    consumer_block = db.relationship('ConsumerBlock', backref='consumer_object')

    def set_consumer_object(self, consumer_obj):
        """Sérialise et stocke l'objet Consumer"""
        self.object_data = pickle.dumps(consumer_obj)

    def get_consumer_object(self):
        """Désérialise et retourne l'objet Consumer"""
        if self.object_data:
            return pickle.loads(self.object_data)
        return None

    def __repr__(self):
        return f'<ConsumerObject {self.consumer_name}>'


class ProducerObject(db.Model):
    __tablename__ = 'producer_objects'

    id = db.Column(db.Integer, primary_key=True)
    producer_block_id = db.Column(db.Integer, db.ForeignKey('producer_block.id'), unique=True, nullable=False)
    producer_name = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    producer_id_number = db.Column(db.BigInteger, default=1234567901000)
    object_data = db.Column(db.LargeBinary, nullable=True)  # Objet sérialisé (pickle)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    # Relation avec ProducerBlock
    producer_block = db.relationship('ProducerBlock', backref='producer_object')

    def set_producer_object(self, producer_obj):
        """Sérialise et stocke l'objet Producer"""
        self.object_data = pickle.dumps(producer_obj)

    def get_producer_object(self):
        """Désérialise et retourne l'objet Producer"""
        if self.object_data:
            return pickle.loads(self.object_data)
        return None

    def __repr__(self):
        return f'<ProducerObject {self.producer_name}>'


# Fonctions d'accès aux objets Consumer et Producer
def get_cons_list():
    """Retourne la liste des objets Consumer depuis SQLAlchemy"""
    consumer_objects = ConsumerObject.query.all()
    consumers = []
    for consumer_obj in consumer_objects:
        consumer = consumer_obj.get_consumer_object()
        if consumer:
            consumers.append(consumer)
    return consumers


def get_prod_list():
    """Retourne la liste des objets Producer depuis SQLAlchemy"""
    producer_objects = ProducerObject.query.all()
    producers = []
    for producer_obj in producer_objects:
        producer = producer_obj.get_producer_object()
        if producer:
            producers.append(producer)
    return producers


def save_consumer(consumer_block_id, consumer_obj, consumer_name, file_path, priorities, ratios):
    """Sauvegarde un objet Consumer dans SQLAlchemy"""
    # Vérifier si l'objet existe déjà
    existing = ConsumerObject.query.filter_by(consumer_block_id=consumer_block_id).first()

    if existing:
        # Mettre à jour l'objet existant
        existing.consumer_name = consumer_name
        existing.file_path = file_path
        existing.priority_list = json.dumps(priorities)
        existing.ratio_list = json.dumps(ratios)
        existing.set_consumer_object(consumer_obj)
    else:
        # Créer un nouvel objet
        new_consumer_obj = ConsumerObject(
            consumer_block_id=consumer_block_id,
            consumer_name=consumer_name,
            file_path=file_path,
            priority_list=json.dumps(priorities),
            ratio_list=json.dumps(ratios)
        )
        new_consumer_obj.set_consumer_object(consumer_obj)
        db.session.add(new_consumer_obj)

    db.session.commit()


def save_producer(producer_block_id, producer_obj, producer_name, file_path):
    """Sauvegarde un objet Producer dans SQLAlchemy"""
    # Vérifier si l'objet existe déjà
    existing = ProducerObject.query.filter_by(producer_block_id=producer_block_id).first()

    if existing:
        # Mettre à jour l'objet existant
        existing.producer_name = producer_name
        existing.file_path = file_path
        existing.set_producer_object(producer_obj)
    else:
        # Créer un nouvel objet
        new_producer_obj = ProducerObject(
            producer_block_id=producer_block_id,
            producer_name=producer_name,
            file_path=file_path
        )
        new_producer_obj.set_producer_object(producer_obj)
        db.session.add(new_producer_obj)

    db.session.commit()


def delete_consumer_object(consumer_block_id):
    """Supprime un objet Consumer de SQLAlchemy"""
    consumer_obj = ConsumerObject.query.filter_by(consumer_block_id=consumer_block_id).first()
    if consumer_obj:
        db.session.delete(consumer_obj)
        db.session.commit()


def delete_producer_object(producer_block_id):
    """Supprime un objet Producer de SQLAlchemy"""
    producer_obj = ProducerObject.query.filter_by(producer_block_id=producer_block_id).first()
    if producer_obj:
        db.session.delete(producer_obj)
        db.session.commit()


# Create database tables
with app.app_context():
    db.create_all()


@app.route('/')
def index():
    text_blocks = TextBlock.query.order_by(TextBlock.date_created.desc()).all()
    consumer_blocks = ConsumerBlock.query.order_by(ConsumerBlock.id).all()
    producer_blocks = ProducerBlock.query.order_by(ProducerBlock.id).all()
    return render_template('index.html', text_blocks=text_blocks, consumer_blocks=consumer_blocks,
                           producer_blocks=producer_blocks)


@app.route('/debug_info')
def debug_info():
    """Route pour vérifier la configuration sur le serveur"""
    # Normaliser les chemins
    upload_path = os.path.normpath(app.config.get('UPLOAD_FOLDER', ''))
    export_path = os.path.normpath(EXPORT_FOLDER)
    
    info = {
        'current_directory': os.getcwd(),
        'upload_folder': upload_path,
        'upload_folder_exists': os.path.exists(upload_path),
        'upload_folder_writable': os.access(upload_path, os.W_OK) if os.path.exists(upload_path) else False,
        'export_folder': export_path,
        'export_folder_exists': os.path.exists(export_path),
        'export_folder_writable': os.access(export_path, os.W_OK) if os.path.exists(export_path) else False,
        'python_version': sys.version,
        'app_directory': os.path.dirname(os.path.abspath(__file__)),
        'permissions_check': check_permissions(),
        'path_separator': os.sep,
        'original_upload_config': str(app.config.get('UPLOAD_FOLDER')),
        'normalized_upload': upload_path,
        'normalized_export': export_path
    }
    
    return jsonify(info)


@app.route('/add', methods=['POST'])
def add_text_block():
    title = request.form['title']
    content = request.form['content']

    new_text_block = TextBlock(title=title, content=content)

    try:
        db.session.add(new_text_block)
        db.session.commit()
        return smart_redirect('/')
    except:
        return 'There was an issue adding your text block'


# Fonctions utilitaires pour la gestion des listes priority/ratio
def get_producer_count():
    """Retourne le nombre de producteurs existants"""
    return ProducerBlock.query.count()


def update_all_consumers_for_new_producer():
    """Met à jour tous les consumers existants quand un nouveau producteur est ajouté"""
    consumer_objects = ConsumerObject.query.all()
    for consumer_obj_record in consumer_objects:
        consumer = consumer_obj_record.get_consumer_object()
        if consumer:
            # Ajouter une valeur pour le nouveau producteur
            consumer.add_producer_values()

            # Sauvegarder l'objet modifié
            consumer_obj_record.set_consumer_object(consumer)
            consumer_obj_record.priority_list = json.dumps(consumer.priority_list)
            consumer_obj_record.ratio_list = json.dumps(consumer.ratio_list)

    if consumer_objects:
        db.session.commit()


def update_all_consumers_for_deleted_producer(producer_index):
    """Met à jour tous les consumers existants quand un producteur est supprimé"""
    consumer_objects = ConsumerObject.query.all()
    for consumer_obj_record in consumer_objects:
        consumer = consumer_obj_record.get_consumer_object()
        if consumer:
            # Supprimer les valeurs correspondant au producteur supprimé
            if producer_index < len(consumer.priority_list):
                consumer.priority_list.pop(producer_index)
            if producer_index < len(consumer.ratio_list):
                consumer.ratio_list.pop(producer_index)

            # Sauvegarder l'objet modifié
            consumer_obj_record.set_consumer_object(consumer)
            consumer_obj_record.priority_list = json.dumps(consumer.priority_list)
            consumer_obj_record.ratio_list = json.dumps(consumer.ratio_list)

    if consumer_objects:
        db.session.commit()


def get_producer_index_by_id(producer_id):
    """Retourne l'index d'un producteur basé sur son ID (ordre de création)"""
    producers = ProducerBlock.query.order_by(ProducerBlock.id).all()
    for index, producer in enumerate(producers):
        if producer.id == producer_id:
            return index
    return -1


@app.route('/add_consumer', methods=['POST'])
def add_consumer_block():
    cons_name = request.form['cons_name']

    # Créer le ConsumerBlock
    new_consumer_block = ConsumerBlock(cons_name=cons_name)

    try:
        db.session.add(new_consumer_block)
        db.session.commit()

        # Obtenir le nombre de producteurs existants
        producer_count = get_producer_count()

        # Créer les listes avec les valeurs par défaut
        priority_list = [0] * producer_count  # 0 pour chaque producteur
        ratio_list = [100] * producer_count  # 100 pour chaque producteur

        # Créer l'objet Consumer avec les listes initialisées
        consumer = Consumer.Consumer(cons_name, cons_name, priority_list, ratio_list)

        # Sauvegarder l'objet Consumer dans SQLAlchemy
        save_consumer(new_consumer_block.id, consumer, cons_name, "", priority_list, ratio_list)

        return jsonify({'success': True, 'message': 'Consommateur ajouté avec succès'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})


@app.route('/add_producer', methods=['POST'])
def add_producer_block():
    prod_name = request.form['prod_name']

    # Créer le ProducerBlock
    new_producer_block = ProducerBlock(prod_name=prod_name)

    try:
        db.session.add(new_producer_block)
        db.session.commit()

        # Créer l'objet Producer sans fichier
        producer = Producer.Producer(prod_name, 1234567901000)

        # Sauvegarder l'objet Producer dans SQLAlchemy
        save_producer(new_producer_block.id, producer, prod_name, "")

        # Mettre à jour tous les consumers existants pour le nouveau producteur
        update_all_consumers_for_new_producer()

        return jsonify({'success': True, 'message': 'Producteur ajouté avec succès'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erreur: {str(e)}'})


@app.route('/update_consumer_data', methods=['POST'])
def update_consumer_data():
    try:
        data = request.get_json()
        consumer_id = data.get('consumer_id')
        producer_index = data.get('producer_index')  # Index du producteur
        field_type = data.get('field_type')  # 'priority' ou 'ratio'
        value = data.get('value')

        consumer_block = ConsumerBlock.query.get_or_404(consumer_id)

        if field_type == 'priority':
            consumer_block.set_priority_for_producer(producer_index, value)
        elif field_type == 'ratio':
            consumer_block.set_ratio_for_producer(producer_index, value)

        return jsonify({'success': True, 'message': 'Données mises à jour'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/delete/<int:id>')
def delete(id):
    text_block_to_delete = TextBlock.query.get_or_404(id)

    try:
        db.session.delete(text_block_to_delete)
        db.session.commit()
        return smart_redirect('/')
    except:
        return 'There was a problem deleting that text block'


@app.route('/delete_consumer/<int:id>')
def delete_consumer(id):
    consumer_block_to_delete = ConsumerBlock.query.get_or_404(id)

    try:
        # Supprimer aussi l'objet Consumer associé
        delete_consumer_object(id)

        db.session.delete(consumer_block_to_delete)
        db.session.commit()
        return smart_redirect('/')
    except:
        return 'There was a problem deleting that consumer block'


@app.route('/delete_producer/<int:id>')
def delete_producer(id):
    producer_block_to_delete = ProducerBlock.query.get_or_404(id)

    try:
        # Obtenir l'index du producteur avant de le supprimer
        producer_index = get_producer_index_by_id(id)

        # Supprimer l'objet Producer associé
        delete_producer_object(id)

        # Supprimer le ProducerBlock
        db.session.delete(producer_block_to_delete)
        db.session.commit()

        # Mettre à jour tous les consumers pour supprimer les valeurs du producteur supprimé
        if producer_index >= 0:
            update_all_consumers_for_deleted_producer(producer_index)

        return smart_redirect('/')
    except Exception as e:
        print(f"Erreur lors de la suppression du producteur : {str(e)}")
        return 'There was a problem deleting that producer block'


@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update(id):
    text_block = TextBlock.query.get_or_404(id)

    if request.method == 'POST':
        text_block.title = request.form['title']
        text_block.content = request.form['content']

        try:
            db.session.commit()
            return smart_redirect('/')
        except:
            return 'There was an issue updating your text block'
    else:
        return render_template('update.html', text_block=text_block)


@app.route('/update_consumer/<int:id>', methods=['GET', 'POST'])
def update_consumer(id):
    consumer_block = ConsumerBlock.query.get_or_404(id)

    if request.method == 'POST':
        consumer_block.cons_name = request.form['cons_name']

        try:
            db.session.commit()
            return smart_redirect('/')
        except:
            return 'There was an issue updating your consumer block'
    else:
        return render_template('update_consumer.html', consumer_block=consumer_block)


@app.route('/update_producer/<int:id>', methods=['GET', 'POST'])
def update_producer(id):
    producer_block = ProducerBlock.query.get_or_404(id)

    if request.method == 'POST':
        producer_block.prod_name = request.form['prod_name']

        try:
            db.session.commit()
            return smart_redirect('/')
        except:
            return 'There was an issue updating your producer block'
    else:
        return render_template('update_producer.html', producer_block=producer_block)


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload_consumer_file', methods=['POST'])
def upload_consumer_file():
    try:
        cons_name = request.form.get('cons_name')
        consumer_id = request.form.get('id')

        # Check if the post request has the file part
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file selected'})

        file = request.files['file']

        # If user does not select file, browser submits empty part without filename
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            # Vérifier que le dossier d'upload existe
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Sauvegarder le fichier
            file.save(filepath)
            
            # Vérifier que le fichier a été sauvegardé
            if not os.path.exists(filepath):
                return jsonify({'success': False, 'message': 'File could not be saved'})

            # Récupérer l'objet Consumer existant
            consumer_obj_record = ConsumerObject.query.filter_by(consumer_block_id=int(consumer_id)).first()
            if consumer_obj_record:
                consumer = consumer_obj_record.get_consumer_object()
                if consumer:
                    # Utiliser la méthode read_consumption pour charger les données
                    consumer.read_consumption(filepath)

                    # Mettre à jour l'enregistrement
                    consumer_obj_record.file_path = filepath
                    consumer_obj_record.set_consumer_object(consumer)
                    consumer_obj_record.priority_list = json.dumps(consumer.priority_list)
                    consumer_obj_record.ratio_list = json.dumps(consumer.ratio_list)
                    db.session.commit()

                    return jsonify({'success': True, 'message': 'File uploaded successfully'})
                else:
                    return jsonify({'success': False, 'message': 'Consumer object could not be retrieved'})
            else:
                return jsonify({'success': False, 'message': 'Consumer object not found'})
        else:
            return jsonify({'success': False, 'message': 'Invalid file type'})
            
    except Exception as e:
        # Log l'erreur complète pour le debugging
        print(f"Error in upload_consumer_file: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'})


@app.route('/upload_producer_file', methods=['POST'])
def upload_producer_file():
    try:
        prod_name = request.form.get('prod_name')
        producer_id = request.form.get('id')

        # Check if the post request has the file part
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file selected'})

        file = request.files['file']

        # If user does not select file, browser submits empty part without filename
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            # Vérifier que le dossier d'upload existe
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Sauvegarder le fichier
            file.save(filepath)
            
            # Vérifier que le fichier a été sauvegardé
            if not os.path.exists(filepath):
                return jsonify({'success': False, 'message': 'File could not be saved'})

            # Récupérer l'objet Producer existant
            producer_obj_record = ProducerObject.query.filter_by(producer_block_id=int(producer_id)).first()
            if producer_obj_record:
                producer = producer_obj_record.get_producer_object()
                if producer:
                    # Utiliser la méthode read_production pour charger les données
                    producer.read_production(filepath)

                    # Mettre à jour l'enregistrement
                    producer_obj_record.file_path = filepath
                    producer_obj_record.set_producer_object(producer)
                    db.session.commit()

                    return jsonify({'success': True, 'message': 'File uploaded successfully', 'filename': filename})
                else:
                    return jsonify({'success': False, 'message': 'Producer object could not be retrieved'})
            else:
                return jsonify({'success': False, 'message': 'Producer object not found'})
        else:
            return jsonify({'success': False, 'message': f'Invalid file type. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'})
            
    except Exception as e:
        # Log l'erreur complète pour le debugging
        print(f"Error in upload_producer_file: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'})


@app.route('/compute_repartition_keys', methods=['POST'])
def compute_repartition_keys():
    global auto_consumption_rate
    global auto_production_rate_global
    global coverage_rate

    global stat_file_list
    global stat_file_generated

    try:
        # Récupérer le type de clés de répartition depuis le formulaire
        key_type = request.form.get('cles', 'default')  # 'default' par défaut si non spécifié

        # Mapping des valeurs du formulaire vers les stratégies
        strategy_mapping = {
            'default': Repartition.Strategy.DYNAMIC_BY_DEFAULT,
            'dynamic': Repartition.Strategy.DYNAMIC,
            'static': Repartition.Strategy.STATIC
        }

        # Récupérer la stratégie correspondante
        strategy = strategy_mapping.get(key_type, Repartition.Strategy.DYNAMIC_BY_DEFAULT)

        print(f"Type de clés sélectionné : {key_type}")
        print(f"Stratégie utilisée : {strategy}")

        # Récupérer les listes depuis SQLAlchemy
        prod_list = get_prod_list()
        cons_list = get_cons_list()

        # Vérifier qu'il y a des producteurs et consommateurs
        if not prod_list:
            return jsonify({'success': False, 'message': 'Aucun producteur ajouté'})

        if not cons_list:
            return jsonify({'success': False, 'message': 'Aucun consommateur ajouté'})

        rep = Repartition.Repartition()
        # Utiliser la stratégie sélectionnée au lieu de DYNAMIC_BY_DEFAULT
        rep.build_rep(prod_list, cons_list, strategy)
        rep.write_repartition_key(prod_list, cons_list, EXPORT_FOLDER, True)

        stat_file_list = rep.generate_statistics(prod_list, cons_list, EXPORT_FOLDER)
        stat_file_generated = True
        rep.generate_monthly_report(prod_list, cons_list, EXPORT_FOLDER, add_cons_mois=False)

        auto_consumption_rate = rep.get_auto_consumption_rate(0)
        print("Taux d'autoconsommation : ", auto_consumption_rate, "%")

        index_cons = 0
        auto_production_rate_global = 0
        for cons in cons_list:
            auto_production_rate = rep.get_auto_production_rate(index_cons)
            auto_production_rate_global += auto_production_rate
            index_cons += 1
        auto_production_rate_global = rep.get_global_auto_production_rate(cons_list)
        print("Taux d'autoproduction global : ", auto_production_rate_global, "%")

        coverage_rate = rep.get_coverage_rate(0, cons_list)
        print("Taux de couverture : ", coverage_rate, "%")

        return jsonify({
            'success': True,
            'message': f'Calcul des clés de répartition terminé avec succès (Stratégie: {key_type})',
            'indicators': {
                'auto_consumption_rate': round(auto_consumption_rate, 2),
                'auto_production_rate_global': round(auto_production_rate_global, 2),
                'coverage_rate': round(coverage_rate, 2)
            }
        })

    except Exception as e:
        print(f"Erreur lors du calcul : {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Erreur lors du calcul : {str(e)}'})


@app.route('/data')
def chart_data():
    global stat_file_generated, stat_file_list, auto_consumption_rate, auto_production_rate_global, coverage_rate

    res = "jour"

    try:
        # Créer votre graphique
        if stat_file_generated and stat_file_list and len(stat_file_list) > 0:
            print(f"Génération du graphique à partir de: {stat_file_list[0]}")
            
            # Vérifier que le fichier existe
            if not os.path.exists(stat_file_list[0]):
                raise FileNotFoundError(f"Le fichier de statistiques {stat_file_list[0]} n'existe pas")
            
            fig = Graph.generate_graph(stat_file_list[0], ';', group=False, resolution=res)

            if not hasattr(fig, 'data') or len(fig.data) == 0:
                raise ValueError("Le graphique généré ne contient aucune donnée")

            fig.update_layout(
                autosize=True,
                margin=dict(autoexpand=True)
            )

            # Convertir les données du graphique
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
                print(f"Trace ajoutée: {trace.name} avec {len(trace.x)} points")

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
                    'auto_consumption_rate': round(auto_consumption_rate, 2),
                    'auto_production_rate_global': round(auto_production_rate_global, 2),
                    'coverage_rate': round(coverage_rate, 2)
                }
            }

            print(f"Graphique créé avec {len(traces)} traces")
            return jsonify(result)

        else:
            print("Aucune donnée de statistiques disponible")
            # Retourner un graphique vide par défaut
            result = {
                'data': [],
                'layout': {
                    'title': 'Aucune donnée disponible - Veuillez calculer les clés de répartition',
                    'xaxis': {'title': 'Date'},
                    'yaxis': {'title': 'Autoconsommation (kWh)'},
                    'legend': {
                        'orientation': 'h',
                        'x': 0.5,
                        'xanchor': 'center',
                        'y': -0.2,
                        'yanchor': 'top'
                    },
                    'annotations': [{
                        'x': 0.5,
                        'y': 0.5,
                        'xref': 'paper',
                        'yref': 'paper',
                        'text': 'Cliquez sur "Calculer les clés de répartitions" pour générer le graphique',
                        'showarrow': False,
                        'font': {'size': 16, 'color': '#666'},
                        'xanchor': 'center',
                        'yanchor': 'middle'
                    }]
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
        import traceback
        traceback.print_exc()
        
        # Retourner un graphique d'erreur
        result = {
            'data': [],
            'layout': {
                'title': 'Erreur lors de la génération du graphique',
                'xaxis': {'title': 'Date'},
                'yaxis': {'title': 'Autoconsommation (kWh)'},
                'legend': {
                    'orientation': 'h',
                    'x': 0.5,
                    'xanchor': 'center',
                    'y': -0.2,
                    'yanchor': 'top'
                },
                'annotations': [{
                    'x': 0.5,
                    'y': 0.5,
                    'xref': 'paper',
                    'yref': 'paper',
                    'text': f'Erreur: {str(e)}',
                    'showarrow': False,
                    'font': {'size': 14, 'color': '#d32f2f'},
                    'xanchor': 'center',
                    'yanchor': 'middle'
                }]
            },
            'indicators': {
                'auto_consumption_rate': 0,
                'auto_production_rate_global': 0,
                'coverage_rate': 0
            }
        }
        return jsonify(result)

# Vérifier les permissions au démarrage
if __name__ == '__main__':
    check_permissions()
    # Pour le développement local
    app.run(debug=True)
else:
    # Pour la production (cPanel)
    check_permissions()