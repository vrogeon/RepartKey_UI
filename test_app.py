# test_app.py - Tests pour vérifier le bon fonctionnement de l'application

import os
import sys
import tempfile
import unittest
from datetime import datetime

# Ajouter le répertoire courant au path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app_auth import app, db
from models import User, Project, ConsumerBlock, ProducerBlock
from forms import CaptchaHelper

class TestRepartKeyAuth(unittest.TestCase):
    """Tests unitaires pour RepartKey avec authentification"""
    
    def setUp(self):
        """Configuration avant chaque test"""
        # Configuration de test
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        self.app = app
        self.client = app.test_client()
        
        # Créer les tables
        with app.app_context():
            db.create_all()
            
            # Créer un utilisateur de test
            self.test_user = User(username='testuser', email='test@example.com')
            self.test_user.set_password('TestPass123')
            db.session.add(self.test_user)
            db.session.commit()
    
    def tearDown(self):
        """Nettoyage après chaque test"""
        with app.app_context():
            db.session.remove()
            db.drop_all()
    
    def login(self, username, password):
        """Helper pour se connecter"""
        return self.client.post('/login', data={
            'username': username,
            'password': password,
            'captcha_answer': '10'  # Valeur arbitraire car CSRF désactivé
        }, follow_redirects=True)
    
    def logout(self):
        """Helper pour se déconnecter"""
        return self.client.get('/logout', follow_redirects=True)
    
    # === Tests d'authentification ===
    
    def test_user_creation(self):
        """Test de création d'utilisateur"""
        with app.app_context():
            user = User(username='newuser', email='new@example.com')
            user.set_password('NewPass123')
            db.session.add(user)
            db.session.commit()
            
            # Vérifier que l'utilisateur existe
            found_user = User.query.filter_by(username='newuser').first()
            self.assertIsNotNone(found_user)
            self.assertEqual(found_user.email, 'new@example.com')
            self.assertTrue(found_user.check_password('NewPass123'))
            self.assertFalse(found_user.check_password('WrongPass'))
    
    def test_login_page(self):
        """Test d'accès à la page de connexion"""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'RepartKey', response.data)
    
    def test_register_page(self):
        """Test d'accès à la page d'inscription"""
        response = self.client.get('/register')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'inscription', response.data.lower())
    
    def test_login_success(self):
        """Test de connexion réussie"""
        response = self.login('testuser', 'TestPass123')
        self.assertEqual(response.status_code, 200)
        # Vérifier qu'on est redirigé vers les projets
        self.assertIn(b'projet', response.data.lower())
    
    def test_login_failure(self):
        """Test de connexion échouée"""
        response = self.login('testuser', 'WrongPassword')
        self.assertIn(b'incorrect', response.data.lower())
    
    def test_logout(self):
        """Test de déconnexion"""
        self.login('testuser', 'TestPass123')
        response = self.logout()
        self.assertIn(b'connect', response.data.lower())
    
    # === Tests CAPTCHA ===
    
    def test_captcha_generation(self):
        """Test de génération de CAPTCHA"""
        question, answer = CaptchaHelper.generate_captcha()
        self.assertIsNotNone(question)
        self.assertIsInstance(answer, int)
        self.assertIn('=', question)
    
    # === Tests de projets ===
    
    def test_project_creation(self):
        """Test de création de projet"""
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            project = Project(
                name='Test Project',
                description='Description test',
                user_id=user.id
            )
            db.session.add(project)
            db.session.commit()
            
            # Vérifier que le projet existe
            found_project = Project.query.filter_by(name='Test Project').first()
            self.assertIsNotNone(found_project)
            self.assertEqual(found_project.user_id, user.id)
            self.assertEqual(found_project.description, 'Description test')
    
    def test_project_ownership(self):
        """Test de propriété des projets"""
        with app.app_context():
            # Créer un deuxième utilisateur
            user2 = User(username='user2', email='user2@example.com')
            user2.set_password('Pass123')
            db.session.add(user2)
            
            # Créer un projet pour le premier utilisateur
            user1 = User.query.filter_by(username='testuser').first()
            project = Project(name='Private Project', user_id=user1.id)
            db.session.add(project)
            db.session.commit()
            
            # Vérifier que le projet appartient au bon utilisateur
            self.assertEqual(project.owner.username, 'testuser')
            self.assertNotEqual(project.owner.username, 'user2')
    
    # === Tests des blocs ===
    
    def test_consumer_block_creation(self):
        """Test de création de ConsumerBlock"""
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            project = Project(name='Test Project', user_id=user.id)
            db.session.add(project)
            db.session.commit()
            
            consumer = ConsumerBlock(
                cons_name='Test Consumer',
                project_id=project.id
            )
            db.session.add(consumer)
            db.session.commit()
            
            # Vérifier
            found_consumer = ConsumerBlock.query.filter_by(cons_name='Test Consumer').first()
            self.assertIsNotNone(found_consumer)
            self.assertEqual(found_consumer.project_id, project.id)
    
    def test_producer_block_creation(self):
        """Test de création de ProducerBlock"""
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            project = Project(name='Test Project', user_id=user.id)
            db.session.add(project)
            db.session.commit()
            
            producer = ProducerBlock(
                prod_name='Test Producer',
                project_id=project.id
            )
            db.session.add(producer)
            db.session.commit()
            
            # Vérifier
            found_producer = ProducerBlock.query.filter_by(prod_name='Test Producer').first()
            self.assertIsNotNone(found_producer)
            self.assertEqual(found_producer.project_id, project.id)
    
    # === Tests de sécurité ===
    
    def test_protected_routes(self):
        """Test que les routes sont protégées"""
        # Sans connexion, on doit être redirigé vers login
        response = self.client.get('/projects')
        self.assertEqual(response.status_code, 302)  # Redirection
        self.assertIn('/login', response.location)
        
        response = self.client.get('/project/1')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)
    
    def test_password_hashing(self):
        """Test que les mots de passe sont bien hachés"""
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            # Le hash ne doit pas être égal au mot de passe
            self.assertNotEqual(user.password_hash, 'TestPass123')
            # Mais la vérification doit fonctionner
            self.assertTrue(user.check_password('TestPass123'))
    
    # === Tests de cascade ===
    
    def test_project_deletion_cascade(self):
        """Test que la suppression d'un projet supprime ses dépendances"""
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            project = Project(name='To Delete', user_id=user.id)
            db.session.add(project)
            db.session.commit()
            
            # Ajouter des blocs
            consumer = ConsumerBlock(cons_name='Consumer', project_id=project.id)
            producer = ProducerBlock(prod_name='Producer', project_id=project.id)
            db.session.add(consumer)
            db.session.add(producer)
            db.session.commit()
            
            # IDs pour vérification
            consumer_id = consumer.id
            producer_id = producer.id
            
            # Supprimer le projet
            db.session.delete(project)
            db.session.commit()
            
            # Vérifier que les blocs sont aussi supprimés
            self.assertIsNone(ConsumerBlock.query.get(consumer_id))
            self.assertIsNone(ProducerBlock.query.get(producer_id))
    
    def test_user_deletion_cascade(self):
        """Test que la suppression d'un utilisateur supprime ses projets"""
        with app.app_context():
            user = User(username='todelete', email='delete@example.com')
            user.set_password('Pass123')
            db.session.add(user)
            db.session.commit()
            
            # Créer un projet
            project = Project(name='User Project', user_id=user.id)
            db.session.add(project)
            db.session.commit()
            
            project_id = project.id
            
            # Supprimer l'utilisateur
            db.session.delete(user)
            db.session.commit()
            
            # Vérifier que le projet est supprimé
            self.assertIsNone(Project.query.get(project_id))


class TestSystemRequirements(unittest.TestCase):
    """Tests des prérequis système"""
    
    def test_python_version(self):
        """Vérifier la version de Python"""
        import sys
        self.assertGreaterEqual(sys.version_info[:2], (3, 7))
    
    def test_required_modules(self):
        """Vérifier que tous les modules requis sont installables"""
        required_modules = [
            'flask',
            'flask_sqlalchemy',
            'flask_login',
            'flask_wtf',
            'wtforms',
            'werkzeug',
            'plotly',
            'pandas',
            'numpy'
        ]
        
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                self.fail(f"Module requis non trouvé: {module}")
    
    def test_directory_creation(self):
        """Test de création des répertoires nécessaires"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Tester la création des dossiers
            courbes_dir = os.path.join(tmpdir, 'Courbes')
            export_dir = os.path.join(tmpdir, 'Export')
            
            os.makedirs(courbes_dir, exist_ok=True)
            os.makedirs(export_dir, exist_ok=True)
            
            self.assertTrue(os.path.exists(courbes_dir))
            self.assertTrue(os.path.exists(export_dir))
            
            # Tester l'écriture
            test_file = os.path.join(courbes_dir, 'test.txt')
            with open(test_file, 'w') as f:
                f.write('test')
            
            self.assertTrue(os.path.exists(test_file))


def run_tests():
    """Fonction principale pour lancer les tests"""
    print("=" * 60)
    print("🧪 TESTS DE L'APPLICATION REPARTKEY")
    print("=" * 60)
    print()
    
    # Créer le suite de tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Ajouter les tests
    suite.addTests(loader.loadTestsFromTestCase(TestRepartKeyAuth))
    suite.addTests(loader.loadTestsFromTestCase(TestSystemRequirements))
    
    # Lancer les tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Résumé
    print()
    print("=" * 60)
    if result.wasSuccessful():
        print("✅ TOUS LES TESTS SONT PASSÉS AVEC SUCCÈS!")
    else:
        print(f"❌ {len(result.failures)} test(s) échoué(s)")
        print(f"❌ {len(result.errors)} erreur(s)")
    print("=" * 60)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)