# models.py - Nouveaux modèles pour l'authentification et les projets

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json
import pickle

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    projects = db.relationship('Project', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Project(db.Model):
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    last_modified = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relations
    text_blocks = db.relationship('TextBlock', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    consumer_blocks = db.relationship('ConsumerBlock', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    producer_blocks = db.relationship('ProducerBlock', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Project {self.name}>'


class TextBlock(db.Model):
    __tablename__ = 'text_blocks'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TextBlock {self.title}>'


class ConsumerBlock(db.Model):
    __tablename__ = 'consumer_blocks'
    
    id = db.Column(db.Integer, primary_key=True)
    cons_name = db.Column(db.String(100), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relation avec ConsumerObject
    consumer_object = db.relationship('ConsumerObject', backref='consumer_block', uselist=False, cascade='all, delete-orphan')

    def get_consumer_object(self):
        """Retourne l'objet Consumer associé"""
        if self.consumer_object:
            return self.consumer_object.get_consumer_object()
        return None

    def get_priority_for_producer(self, producer_index):
        """Retourne la priorité pour un producteur spécifique"""
        consumer = self.get_consumer_object()
        if consumer and producer_index < len(consumer.priority_list):
            return consumer.priority_list[producer_index]
        return 0

    def get_ratio_for_producer(self, producer_index):
        """Retourne le ratio pour un producteur spécifique"""
        consumer = self.get_consumer_object()
        if consumer and producer_index < len(consumer.ratio_list):
            return consumer.ratio_list[producer_index]
        return 0

    def set_priority_for_producer(self, producer_index, value):
        """Définit la priorité pour un producteur spécifique"""
        if self.consumer_object:
            consumer = self.consumer_object.get_consumer_object()
            if consumer:
                while len(consumer.priority_list) <= producer_index:
                    consumer.priority_list.append(0)
                consumer.priority_list[producer_index] = int(value)
                
                self.consumer_object.set_consumer_object(consumer)
                self.consumer_object.priority_list = json.dumps(consumer.priority_list)
                db.session.commit()

    def set_ratio_for_producer(self, producer_index, value):
        """Définit le ratio pour un producteur spécifique"""
        if self.consumer_object:
            consumer = self.consumer_object.get_consumer_object()
            if consumer:
                while len(consumer.ratio_list) <= producer_index:
                    consumer.ratio_list.append(0)
                consumer.ratio_list[producer_index] = int(value)
                
                self.consumer_object.set_consumer_object(consumer)
                self.consumer_object.ratio_list = json.dumps(consumer.ratio_list)
                db.session.commit()

    def get_file_name(self):
        """Retourne le nom du fichier associé au consommateur"""
        if self.consumer_object and self.consumer_object.file_path:
            import os
            return os.path.basename(self.consumer_object.file_path)
        return None
    
    def has_file(self):
        """Vérifie si un fichier est associé au consommateur"""
        return self.get_file_name() is not None

    def __repr__(self):
        return f'<ConsumerBlock {self.cons_name}>'


class ProducerBlock(db.Model):
    __tablename__ = 'producer_blocks'
    
    id = db.Column(db.Integer, primary_key=True)
    prod_name = db.Column(db.String(100), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relation avec ProducerObject
    producer_object = db.relationship('ProducerObject', backref='producer_block', uselist=False, cascade='all, delete-orphan')

    def get_file_name(self):
        """Retourne le nom du fichier associé au producteur"""
        if self.producer_object and self.producer_object.file_path:
            import os
            return os.path.basename(self.producer_object.file_path)
        return None
    
    def has_file(self):
        """Vérifie si un fichier est associé au producteur"""
        return self.get_file_name() is not None

    def __repr__(self):
        return f'<ProducerBlock {self.prod_name}>'


class ConsumerObject(db.Model):
    __tablename__ = 'consumer_objects'

    id = db.Column(db.Integer, primary_key=True)
    consumer_block_id = db.Column(db.Integer, db.ForeignKey('consumer_blocks.id'), unique=True, nullable=False)
    consumer_name = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(255), nullable=True)
    priority_list = db.Column(db.Text, default='[]')
    ratio_list = db.Column(db.Text, default='[]')
    object_data = db.Column(db.LargeBinary, nullable=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

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
    producer_block_id = db.Column(db.Integer, db.ForeignKey('producer_blocks.id'), unique=True, nullable=False)
    producer_name = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(255), nullable=True)
    producer_id_number = db.Column(db.BigInteger, default=1234567901000)
    object_data = db.Column(db.LargeBinary, nullable=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

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