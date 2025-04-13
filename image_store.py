from flask import Flask, request, jsonify, render_template, send_from_directory, send_file, redirect, url_for, session, flash
import os
import pickle
import mysql.connector
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text
from image_handler import convert_image_to_face_id, compare_faces
from werkzeug.security import generate_password_hash, check_password_hash
from flask_session import Session
from werkzeug.utils import secure_filename
import zipfile
import io
import random
import string
from functools import wraps
import face_recognition

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your_default_secret_key")  # Change to use environment variables
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "mysql+mysqlconnector://root:pandav91@localhost/face_matching")  # Use env for DB URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db = SQLAlchemy(app)

UPLOAD_FOLDER = os.path.join(os.getcwd(), "images")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# ------------------ Models ------------------
class Face(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    face_id = db.Column(db.String(255), unique=True, nullable=False)
    face_encoding = db.Column(db.LargeBinary, nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

class Album(db.Model):
    __tablename__ = 'user_albums'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('face.id', ondelete='CASCADE'), nullable=False)
    album_name = db.Column(db.String(255), nullable=False)
    album_code = db.Column(db.String(4), nullable=False)
    images = db.relationship('AlbumImage', backref='album', cascade="all, delete", lazy=True)

class AlbumImage(db.Model):
    __tablename__ = 'album_images'
    id = db.Column(db.Integer, primary_key=True)
    album_id = db.Column(db.Integer, db.ForeignKey('user_albums.id'), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)

class AlbumMember(db.Model):
    __tablename__ = 'album_members'
    id = db.Column(db.Integer, primary_key=True)
    album_code = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('face.id'), nullable=False)

with app.app_context():
    db.create_all()

def generate_unique_album_code():
    while True:
        code = ''.join(random.choices(string.digits, k=4))
        if not Album.query.filter_by(album_code=code).first():
            return code

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def compare_faces(uploaded_encoding, album_encodings):
    matched_indices = []
    for idx, album_encoding in enumerate(album_encodings):
        if uploaded_encoding is not None and album_encoding is not None:
            matches = face_recognition.compare_faces([album_encoding], uploaded_encoding)
            if matches[0]:
                matched_indices.append(idx)
    return matched_indices

def get_face_encoding_for_image(image_path):
    image = face_recognition.load_image_file(image_path)
    face_encodings = face_recognition.face_encodings(image)

    if face_encodings:
        return face_encodings[0]
    return None

# ------------------ Auth Routes ------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        face_id = request.form['face_id']
        image = request.files['image']

        if Face.query.filter_by(email=email).first():
            return jsonify({"error": "Email already registered"}), 409

        image_filename = f"{face_id}.jpg"
        image_path = os.path.join(UPLOAD_FOLDER, image_filename)
        image.save(image_path)

        face_encoding = convert_image_to_face_id(image_path, image.filename)
        if face_encoding is None:
            os.remove(image_path)
            return jsonify({"error": "No face detected in the image"}), 400

        encoding_binary = pickle.dumps(face_encoding)
        new_user = Face(face_id=face_id, email=email, image_path=image_path, face_encoding=encoding_binary)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        session['user_id'] = new_user.id
        
        user_id = new_user.id
        user_albums = Album.query.filter_by(user_id=user_id).all()

        album_results = []

        for album in user_albums:
            album_images = AlbumImage.query.filter_by(album_id=album.id).all()
            matched_images = []
            other_images = []

            for image in album_images:
                image_path = os.path.join(UPLOAD_FOLDER, "uploads", str(album.id), os.path.basename(image.image_path))
                album_face_encoding = convert_image_to_face_id(image_path, image.image_path)
                
                if album_face_encoding is None:
                    continue

                is_match, similarity_score = compare_faces(face_encoding, album_face_encoding)
                if is_match:
                    matched_images.append({
                        "image_url": url_for('uploaded_file', album_id=album.id, filename=os.path.basename(image.image_path)),
                        "similarity": round((1 - similarity_score) * 100, 2)
                    })
                else:
                    other_images.append({
                        "image_url": url_for('uploaded_file', album_id=album.id, filename=os.path.basename(image.image_path))
                    })
            
            album_results.append({
                "album_name": album.album_name,
                "matched_images": matched_images,
                "other_images": other_images
            })

        flash("Account created successfully! Please log in to continue.", "success")
        return redirect(url_for('login'))

    return render_template("signup.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = Face.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            return redirect(url_for('homepage'))
        else:
            flash("Invalid email or password", "error")
            return redirect(url_for('login'))

    return render_template("login.html")

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

# ------------------ Album Routes ------------------
@app.route('/homepage')
@login_required
def homepage():
    user_id = session['user_id']
    user = Face.query.get(user_id)

    created_albums = Album.query.filter_by(user_id=user_id).all()
    joined_codes = [code for (code,) in db.session.query(AlbumMember.album_code).filter_by(user_id=user_id).all()]
    joined_albums = Album.query.filter(Album.album_code.in_(joined_codes)).all()
    all_albums = created_albums + joined_albums

    albums_data = []
    
    for album in all_albums:
        creator = Face.query.get(album.user_id)
        images = AlbumImage.query.filter_by(album_id=album.id).all()
        image_paths = [url_for('uploaded_file', album_id=album.id, filename=os.path.basename(img.image_path)) for img in images]

        album_face_encodings = []
        for img in images:
            face_encoding = get_face_encoding_for_image(img.image_path)
            album_face_encodings.append(face_encoding)

        uploaded_face_encoding = get_face_encoding_for_image(user.image_path)
        matched_face_indices = compare_faces(uploaded_face_encoding, album_face_encodings)

        matched_images = [image_paths[idx] for idx in matched_face_indices]

        albums_data.append({
            'album_id': album.id,
            'album_name': album.album_name,
            'album_code': album.album_code,
            'creator_username': creator.face_id if creator else "Unknown",
            'images': image_paths,
            'matched_images': matched_images
        })

    return render_template('homepage.html', user_albums=albums_data)

@app.route('/create_album_page', methods=['GET', 'POST'])
@login_required
def create_album_page():
    if request.method == "POST":
        album_name = request.form.get("album_name")
        files = request.files.getlist("images")

        if not album_name or not files or files[0].filename == '':
            return "Album name and at least one image are required", 400

        user_id = session['user_id']
        album_code = generate_unique_album_code()
        new_album = Album(user_id=user_id, album_name=album_name, album_code=album_code)
        db.session.add(new_album)
        db.session.commit()

        album_id = new_album.id
        album_folder = os.path.join(app.config["UPLOAD_FOLDER"], "uploads", str(album_id))
        os.makedirs(album_folder, exist_ok=True)

        for file in files:
            if file.filename == '' or not allowed_file(file.filename):
                continue

            filename = secure_filename(file.filename)
            file_path = os.path.join("images/uploads", str(album_id), filename)
            file.save(os.path.join(album_folder, filename))
            db.session.add(AlbumImage(album_id=album_id, image_path=file_path))

        db.session.commit()
        return redirect(url_for("homepage"))

    return render_template("create_album.html")

@app.route('/join_album', methods=['GET', 'POST'])
@login_required
def join_album():
    if request.method == 'POST':
        album_code = request.form['album_code']
        user_id = session['user_id']

        album = Album.query.filter_by(album_code=album_code).first()
        if not album:
            flash('Invalid album code!', 'error')
            return redirect(url_for('join_album'))

        if AlbumMember.query.filter_by(album_code=album_code, user_id=user_id).first():
            flash('You’ve already joined this album.', 'info')
            return redirect(url_for('homepage'))

        db.session.add(AlbumMember(album_code=album_code, user_id=user_id))
        db.session.commit()
        flash('Album joined successfully!', 'success')
        return redirect(url_for('homepage'))

    return render_template('join_album.html')

@app.route('/album/<int:album_id>')
@login_required
def view_album(album_id):
    album = Album.query.get_or_404(album_id)
    images = AlbumImage.query.filter_by(album_id=album.id).all()
    return render_template('view_album.html', album=album, images=images)

@app.route('/uploads/<int:album_id>/<filename>')
def uploaded_file(album_id, filename):
    return send_from_directory(os.path.join('images', 'uploads', str(album_id)), filename)

@app.route('/download_album/<int:album_id>')
@login_required
def download_album(album_id):
    images = AlbumImage.query.filter_by(album_id=album_id).all()

    album_folder = os.path.join(app.config["UPLOAD_FOLDER"], "uploads", str(album_id))
    zip_filename = f"album_{album_id}.zip"
    zip_path = os.path.join(app.config["UPLOAD_FOLDER"], zip_filename)

    with zipfile.ZipFile(zip_path, 'w') as album_zip:
        for img in images:
            img_path = os.path.join(album_folder, os.path.basename(img.image_path))
            album_zip.write(img_path, os.path.basename(img.image_path))

    return send_file(zip_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
