from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime
import os

import io
import csv

import Consumer
import Producer
import Repartition
import Graph

import plotly.graph_objects as go
import plotly.utils
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///textblocks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

app.config['UPLOAD_FOLDER'] = 'C:\\Pro\\Git\\RepartKey_UI\\Courbes\\'
EXPORT_FOLDER = 'C:\\Pro\\Git\\RepartKey_UI\\Export\\'
ALLOWED_EXTENSIONS = {'csv'}

auto_consumption_rate = 0
auto_production_rate_global = 0
coverage_rate = 0

cons_list = []
prod_list = []
stat_file_list = []

# Global variables used to manage interactions between different blocs
stat_file_generated = False

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
    priority = 0
    ratio = 0

    def __repr__(self):
        return f'<ConsumerBlock>'

class ProducerBlock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prod_name = db.Column(db.String(100), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ConsumerBlock>'


# Create database tables
with app.app_context():
    db.create_all()


@app.route('/')
def index():
    text_blocks = TextBlock.query.order_by(TextBlock.date_created.desc()).all()
    consumer_blocks = ConsumerBlock.query.order_by(ConsumerBlock.id).all()
    producer_blocks = ProducerBlock.query.order_by(ProducerBlock.id).all()
    return render_template('index.html', text_blocks=text_blocks, consumer_blocks=consumer_blocks, producer_blocks=producer_blocks)


@app.route('/add', methods=['POST'])
def add_text_block():
    title = request.form['title']
    content = request.form['content']

    new_text_block = TextBlock(title=title, content=content)

    try:
        db.session.add(new_text_block)
        db.session.commit()
        return redirect('/')
    except:
        return 'There was an issue adding your text block'

@app.route('/add_consumer', methods=['POST'])
def add_consumer_block():
    cons_name = request.form['cons_name']

    new_consumer_block = ConsumerBlock(cons_name=cons_name)

    try:
        db.session.add(new_consumer_block)
        db.session.commit()
        return redirect('/')
    except Exception as e:
        return 'There was an issue adding your consumer:'+ e

@app.route('/add_producer', methods=['POST'])
def add_producer_block():
    prod_name = request.form['prod_name']

    new_producer_block = ProducerBlock(prod_name=prod_name)

    try:
        db.session.add(new_producer_block)
        db.session.commit()
        return redirect('/')
    except Exception as e:
        return 'There was an issue adding your producer:'+ e

@app.route('/delete/<int:id>')
def delete(id):
    text_block_to_delete = TextBlock.query.get_or_404(id)

    try:
        db.session.delete(text_block_to_delete)
        db.session.commit()
        return redirect('/')
    except:
        return 'There was a problem deleting that text block'

@app.route('/delete_consumer/<int:id>')
def delete_consumer(id):
    consumer_block_to_delete = ConsumerBlock.query.get_or_404(id)

    try:
        db.session.delete(consumer_block_to_delete)
        db.session.commit()
        return redirect('/')
    except:
        return 'There was a problem deleting that consumer block'

@app.route('/delete_producer/<int:id>')
def delete_producer(id):
    producer_block_to_delete = ProducerBlock.query.get_or_404(id)

    try:
        db.session.delete(producer_block_to_delete)
        db.session.commit()
        return redirect('/')
    except:
        return 'There was a problem deleting that producer block'

@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update(id):
    text_block = TextBlock.query.get_or_404(id)

    if request.method == 'POST':
        text_block.title = request.form['title']
        text_block.content = request.form['content']

        try:
            db.session.commit()
            return redirect('/')
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
            return redirect('/')
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
            return redirect('/')
        except:
            return 'There was an issue updating your producer block'
    else:
        return render_template('update_producer.html', producer_block=producer_block)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_consumer_file', methods=['POST'])
def upload_consumer_file():
    cons_name = request.form.get('cons_name')
    id = request.form.get('id')
    priority = request.form.get('priority')
    ratio = request.form.get('ratio')

    # Check if the post request has the file part
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file selected'})

    file = request.files['file']

    # If user does not select file, browser submits empty part without filename
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        consumer = Consumer.Consumer(cons_name, cons_name, [0], [50], filepath)
        cons_list.append(consumer)

        return jsonify({'success': True, 'message': 'File uploaded successfully'})
    else:
        return jsonify({'success': False, 'message': 'Invalid file type'})

@app.route('/upload_producer_file', methods=['POST'])
def upload_producer_file():
    prod_name = request.form.get('prod_name')

    # Check if the post request has the file part
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file selected'})

    file = request.files['file']

    # If user does not select file, browser submits empty part without filename
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        producer = Producer.Producer(prod_name, 1234567901000, filepath)
        prod_list.append(producer)

        return jsonify({'success': True, 'message': 'File uploaded successfully', 'filename': filename})
    else:
        return jsonify({'success': False, 'message': f'Invalid file type. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'})


@app.route('/compute_repartition_keys', methods=['POST'])
def compute_repartition_keys():
    global auto_consumption_rate
    global auto_production_rate_global
    global coverage_rate

    global stat_file_list
    global stat_file_generated

    try:
        # Vérifier qu'il y a des producteurs et consommateurs
        if not prod_list:
            return jsonify({'success': False, 'message': 'Aucun producteur ajouté'})

        if not cons_list:
            return jsonify({'success': False, 'message': 'Aucun consommateur ajouté'})

        # Get all information for test
        # prod_list.append(
        #     Producer.Producer('Prod1', 1234567901000,
        #                       app.config['UPLOAD_FOLDER'] + 'Simu_Prod_Enerev_100.csv'))
        #
        # cons_list.append(Consumer.Consumer('Parking_Harmony1','Parking_Harmony1',[ 0 ], [ 50 ],
        #                                    app.config['UPLOAD_FOLDER'] + 'Parking_Harmony1_Conso_202312_202412_V1.csv'))
        # cons_list.append(Consumer.Consumer('Parking_Harmony2','Parking_Harmony2',[ 0 ], [ 50 ],
        #                                    app.config['UPLOAD_FOLDER'] + 'Parking_Harmony2_Conso_202312_202412_V5.csv'))
        # cons_list.append(Consumer.Consumer('Particuliers', 'Particuliers', [1], [100],
        #                                    app.config['UPLOAD_FOLDER'] + 'Simu_50_particuliers.csv'))
        # cons_list.append(Consumer.Consumer('PtiteEchoppe', 'PtiteEchoppe', [2], [50],
        #                                    app.config['UPLOAD_FOLDER'] + 'Simu_PtiteEchoppe.csv'))
        # cons_list.append(Consumer.Consumer('Azimut', 'Azimut', [2], [50],
        #                                    app.config['UPLOAD_FOLDER'] + 'Simu_Azimut.csv'))

        # End test

        rep = Repartition.Repartition()
        rep.build_rep(prod_list, cons_list, Repartition.Strategy.DYNAMIC_BY_DEFAULT)
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
            'message': 'Calcul des clés de répartition terminé avec succès',
            'indicators': {
                'auto_consumption_rate': round(auto_consumption_rate, 2),
                'auto_production_rate_global': round(auto_production_rate_global, 2),
                'coverage_rate': round(coverage_rate, 2)
            }
        })

    except Exception as e:
        print(f"Erreur lors du calcul : {str(e)}")
        return jsonify({'success': False, 'message': f'Erreur lors du calcul : {str(e)}'})


@app.route('/data')
def chart_data():
    global stat_file_generated

    res = "jour"

    # compute_repartition_keys()

    # Créer votre graphique
    if stat_file_generated:
        fig = go.Figure()

        fig = Graph.generate_graph(stat_file_list[0],
                                   ';',
                                   group=False,
                                   resolution=res)

        fig.update_layout(
            autosize=True,
            # Forcer la configuration responsive
            margin=dict(autoexpand=True)
        )

        # Version ultra-simple
        traces = []
        for trace in fig.data:
            traces.append({
                'type': 'scatter',
                'mode': 'lines',
                'fill': 'tonexty' if len(traces) > 0 else 'tozeroy',
                'stackgroup': 'one',
                'name': trace.name,
                'x': [str(x) for x in trace.x],
                'y': [float(str(y)) for y in trace.y]  # Double conversion pour être sûr
            })

        result = {
            'data': traces,
            'layout': {
                'title': 'Autoconsommation cumulée par ' + res,
                'xaxis': {'title': 'Date'},
                'yaxis': {'title': 'Autoconsommation (kWh)'},
                'legend': {
                    'orientation': 'h',  # Orientation horizontale
                    'x': 0.5,  # Centré horizontalement
                    'xanchor': 'center',  # Ancrage au centre
                    'y': -0.2,  # Position en bas du graphique
                    'yanchor': 'top'  # Ancrage par le haut de la légende
                }
            },
            'indicators': {
                'auto_consumption_rate': auto_consumption_rate,
                'auto_production_rate_global': auto_production_rate_global,
                'coverage_rate': coverage_rate
            }
        }

        return jsonify(result)

    else:
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
                # Ajouter une annotation pour guider l'utilisateur
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


if __name__ == '__main__':
    app.run(debug=False)