import os
import io
import pickle
import mysql.connector
from flask import Flask, request, jsonify, render_template, send_file, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_session import Session

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SESSION_COOKIE_NAME'] = 'session'


# Configure database connection
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+mysqlconnector://root:pandav91@localhost/snapsearch"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db = SQLAlchemy(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------- USER MODEL ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    face_id = db.Column(db.String(255), unique=True, nullable=False)
    face_encoding = db.Column(db.LargeBinary, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

# ---------- ALBUM MODEL ----------
class Album(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    album_id = db.Column(db.Integer, db.ForeignKey('album.id'), nullable=False)
    image_data = db.Column(db.LargeBinary, nullable=False)  # Make sure this line is there

    album_name = db.Column(db.String(255), nullable=False)

    user = db.relationship('User', backref=db.backref('albums', lazy=True))

# ---------- ALBUM IMAGES MODEL ----------
class AlbumImages(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    album_id = db.Column(db.Integer, db.ForeignKey('album.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_data = db.Column(db.LargeBinary, nullable=False)

    album = db.relationship('Album', backref=db.backref('images', lazy=True))
    user = db.relationship('User', backref=db.backref('uploaded_images', lazy=True))

# Create tables
with app.app_context():
    db.create_all()

# ---------- USER AUTHENTICATION ----------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        face_id = request.form['face_id']
        image = request.files['image']

        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email already registered"}), 409

        image_filename = f"{face_id}.jpg"
        image_path = os.path.join(UPLOAD_FOLDER, image_filename)
        image.save(image_path)

        face_encoding = pickle.dumps(image.read())  # Dummy encoding, replace with real face encoding logic

        new_user = User(face_id=face_id, email=email, face_encoding=face_encoding)
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template("signup.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            return jsonify({"error": "Invalid email or password"}), 401

    return render_template("login.html")

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

# ---------- DASHBOARD ----------
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template("dashboard.html")

# ---------- CREATE OR JOIN ALBUM ----------
@app.route('/create-album', methods=['GET', 'POST'])
def create_album():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        album_name = request.form['album_name']
        images = request.files.getlist('images')

        if not album_name or len(images) == 0:
            return jsonify({"error": "Missing album name or images"}), 400

        # Create a new album entry
        new_album = Album(user_id=session['user_id'], album_name=album_name)
        db.session.add(new_album)
        db.session.commit()  # Commit to get album ID

        # Save images in album_images table
        for image in images:
            image_binary = image.read()
            new_image = AlbumImages(album_id=new_album.id, user_id=session['user_id'], image_data=image_binary)
            db.session.add(new_image)

        db.session.commit()
        return redirect(url_for('view_album', album_name=album_name))

    return render_template("create_album.html")

@app.route("/upload-album", methods=["POST"])
def upload_album():
    return "Album uploaded successfully", 200

@app.route('/join-album', methods=['POST'])
def join_album():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    album_name = request.form['album_name']
    album = Album.query.filter_by(album_name=album_name).first()

    if album:
        return redirect(url_for('view_album', album_name=album_name))
    else:
        return jsonify({"error": "Album not found"}), 404

# ---------- DISPLAY ALBUM ----------
@app.route('/view-album/<album_name>')
def view_album(album_name):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    album = Album.query.filter_by(album_name=album_name, user_id=session['user_id']).first()
    if not album:
        return jsonify({"error": "Album not found"}), 404

    images = AlbumImages.query.filter_by(album_id=album.id).all()
    image_urls = [f"/get-image/{image.id}" for image in images]

    return render_template("gallery.html", album_name=album_name, image_urls=image_urls)

@app.route('/get-image/<int:image_id>')
def get_image(image_id):
    image = AlbumImages.query.get(image_id)
    if image:
        return send_file(io.BytesIO(image.image_data), mimetype="image/jpeg")
    else:
        return jsonify({"error": "Image not found"}), 404

# ---------- RUN APP ----------
if __name__ == '__main__':
    app.run(debug=True, port=5000)
