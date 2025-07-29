from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///textblocks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'csv'}

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
    # Check if the post request has the file part
    if 'file' not in request.files:
        flash('No file selected')
        return redirect(request.url)

    file = request.files['file']

    # If user does not select file, browser submits empty part without filename
    if file.filename == '':
        flash('No file selected')
        return redirect(request.url)

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Process the file here (read contents, parse, etc.)
        file_info = process_uploaded_file(filepath)

        flash(f'File {filename} uploaded successfully!')
        return render_template('upload.html', file_info=file_info, filename=filename)
    else:
        flash('Invalid file type. Allowed types: txt, pdf, png, jpg, jpeg, gif, csv')
        return redirect(request.url)

@app.route('/upload_producer_file', methods=['POST'])
def upload_producer_file():
    # Check if the post request has the file part
    if 'file' not in request.files:
        flash('No file selected')
        return redirect(request.url)

    file = request.files['file']

    # If user does not select file, browser submits empty part without filename
    if file.filename == '':
        flash('No file selected')
        return redirect(request.url)

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Process the file here (read contents, parse, etc.)
        file_info = process_uploaded_file(filepath)

        flash(f'File {filename} uploaded successfully!')
        return render_template('upload.html', file_info=file_info, filename=filename)
    else:
        flash('Invalid file type. Allowed types: txt, pdf, png, jpg, jpeg, gif, csv')
        return redirect(request.url)


def process_uploaded_file(filepath):
    """Process the uploaded file and return information about it"""
    file_info = {
        'size': os.path.getsize(filepath),
        'name': os.path.basename(filepath)
    }

    # Example: Read text file contents
    if filepath.endswith('.txt'):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                file_info['content'] = f.read()[:500]  # First 500 characters
        except Exception as e:
            file_info['error'] = str(e)

    # Example: Process CSV file
    elif filepath.endswith('.csv'):
        try:
            import pandas as pd
            df = pd.read_csv(filepath)
            file_info['rows'] = len(df)
            file_info['columns'] = list(df.columns)
        except Exception as e:
            file_info['error'] = str(e)

    return file_info





if __name__ == '__main__':
    app.run(debug=False)