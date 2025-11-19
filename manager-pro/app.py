# app.py
from flask import Flask, render_template, request, jsonify, send_from_directory, url_for, flash, redirect
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, File, Folder
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super_secret_key_2025_change_me'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200 Mo max

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialisation
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

# ==================== AUTH ====================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Utilisateur déjà existant')
            return redirect('/register')
        user = User(username=username, password=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        flash('Inscription réussie ! Connectez-vous')
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect('/')
        flash('Identifiants incorrects')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

# ==================== PAGE PRINCIPALE + DASHBOARD ====================
@app.route('/')
@app.route('/folder/<int:folder_id>')
@login_required
def index(folder_id=None):
    current_folder = Folder.query.get(folder_id) if folder_id else None
    if current_folder and current_folder.user_id != current_user.id:
        return "Accès refusé", 403

    # ── STATISTIQUES GLOBALES ──
    total_folders = Folder.query.filter_by(user_id=current_user.id).count()
    total_files = File.query.filter_by(user_id=current_user.id).count()

    total_bytes = 0
    for f in File.query.filter_by(user_id=current_user.id).all():
        path = os.path.join(app.config['UPLOAD_FOLDER'], f.filename)
        if os.path.exists(path):
            total_bytes += os.path.getsize(path)

    if total_bytes < 1024**2:
        storage = f"{total_bytes/1024:.1f} Ko"
    elif total_bytes < 1024**3:
        storage = f"{total_bytes/(1024**2):.2f} Mo"
    elif total_bytes < 1024**4:
        storage = f"{total_bytes/(1024**3):.2f} Go"
    else:
        storage = f"{total_bytes/(1024**4):.2f} To"

    percent = min(100, round(total_bytes / (100 * 1024**3) * 100, 1))  # limite 100 Go

    # ── CONTENU DU DOSSIER ──
    folders = Folder.query.filter_by(user_id=current_user.id, parent_id=folder_id).all()
    files = File.query.filter_by(user_id=current_user.id, folder_id=folder_id)\
                      .order_by(File.upload_date.desc()).all()

    breadcrumb = []
    tmp = current_folder
    while tmp:
        breadcrumb.append({'id': tmp.id, 'name': tmp.name})
        tmp = tmp.parent
    breadcrumb.reverse()

    files_data = []
    for f in files:
        path = os.path.join(app.config['UPLOAD_FOLDER'], f.filename)
        size = os.path.getsize(path) if os.path.exists(path) else 0
        files_data.append({
            'id': f.id,
            'name': f.original_name,
            'filename': f.filename,
            'size': size,
            'date': f.upload_date.strftime('%d/%m/%Y %H:%M'),
            'url': url_for('download_file', file_id=f.id),
            'preview_url': url_for('preview_file', file_id=f.id),
            'share_url': url_for('share_file', file_id=f.id, _external=True)
        })

    return render_template('index.html',
                           files=files_data,
                           folders=folders,
                           current_folder=current_folder,
                           breadcrumb=breadcrumb,
                           current_folder_id=folder_id or 'null',
                           stats={'folders': total_folders, 'files': total_files,
                                  'storage': storage, 'percentage': percent})

# ==================== UPLOAD ====================
@app.route('/upload', methods=['POST'])
@login_required
def upload():
    folder_id = request.form.get('current_folder_id')
    folder_id = int(folder_id) if folder_id and folder_id != 'null' else None

    for file in request.files.getlist('files'):
        if file and file.filename:
            orig = file.filename
            ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            fname = secure_filename(f"{ts}_{orig}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            db_file = File(filename=fname, original_name=orig,
                           folder_id=folder_id, user_id=current_user.id)
            db.session.add(db_file)
    db.session.commit()
    return jsonify(success=True)

# ==================== AUTRES ROUTES ====================
@app.route('/download/<int:file_id>')
@login_required
def download_file(file_id):
    f = File.query.get_or_404(file_id)
    if f.user_id != current_user.id: return "Accès refusé", 403
    return send_from_directory(app.config['UPLOAD_FOLDER'], f.filename, as_attachment=True)

@app.route('/preview/<int:file_id>')
@login_required
def preview_file(file_id):
    f = File.query.get_or_404(file_id)
    if f.user_id != current_user.id: return "Accès refusé", 403
    if not f.filename.lower().endswith('.pdf'): return "PDF uniquement", 400
    return send_from_directory(app.config['UPLOAD_FOLDER'], f.filename)

@app.route('/delete/<int:file_id>', methods=['DELETE'])
@login_required
def delete_file(file_id):
    f = File.query.get_or_404(file_id)
    if f.user_id != current_user.id: return jsonify(error="Accès refusé"), 403
    try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], f.filename))
    except: pass
    db.session.delete(f)
    db.session.commit()
    return jsonify(success=True)

@app.route('/share/<int:file_id>')
def share_file(file_id):
    f = File.query.get(file_id)
    if not f: return "Introuvable", 404
    return send_from_directory(app.config['UPLOAD_FOLDER'], f.filename)

@app.route('/file/move/<int:file_id>', methods=['POST'])
@login_required
def move_file(file_id):
    f = File.query.get_or_404(file_id)
    if f.user_id != current_user.id: return jsonify(error="Accès refusé"), 403
    f.folder_id = request.json.get('folder_id')
    db.session.commit()
    return jsonify(success=True)

@app.route('/folder/create', methods=['POST'])
@login_required
def create_folder():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    pid = data.get('parent_id')
    if not name: return jsonify(error="Nom requis"), 400
    if pid in ('null', '', None):
        pid = None
    else:
        pid = int(pid)
    folder = Folder(name=name, user_id=current_user.id, parent_id=pid)
    db.session.add(folder)
    db.session.commit()
    return jsonify(id=folder.id, name=folder.name)

@app.route('/folder/rename/<int:folder_id>', methods=['POST'])
@login_required
def rename_folder(folder_id):
    f = Folder.query.get_or_404(folder_id)
    if f.user_id != current_user.id: return jsonify(error="Accès refusé"), 403
    f.name = request.json.get('name', '').strip()
    db.session.commit()
    return jsonify(success=True)

@app.route('/folder/delete/<int:folder_id>', methods=['DELETE'])
@login_required
def delete_folder(folder_id):
    f = Folder.query.get_or_404(folder_id)
    if f.user_id != current_user.id: return jsonify(error="Accès refusé"), 403
    File.query.filter_by(folder_id=folder_id).update({'folder_id': None})
    Folder.query.filter_by(parent_id=folder_id).delete()
    db.session.delete(f)
    db.session.commit()
    return jsonify(success=True)

if __name__ == '__main__':
    app.run(debug=True)