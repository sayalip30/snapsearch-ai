from flask import Flask, request, jsonify, render_template, send_from_directory, send_file, redirect, url_for, session
import os
import pickle
import mysql.connector
import io
from flask_sqlalchemy import SQLAlchemy
from image_handler import convert_image_to_face_id, compare_faces
from werkzeug.security import generate_password_hash, check_password_hash
from flask_session import Session  # Import Flask-Session
from flask import send_from_directory
from werkzeug.utils import secure_filename  # Add this if not imported



app = Flask(__name__)
app.secret_key = "1212"  # Change this to a strong, random key
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+mysqlconnector://root:pandav91@localhost/face_matching"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Configure Flask-Session
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"  # Store session data in files
Session(app)  # Initialize Flask-Session

db = SQLAlchemy(app)

# ------------------- Face Recognition User Model -------------------
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

with app.app_context():
    db.create_all()

UPLOAD_FOLDER = os.path.join(os.getcwd(), "images")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ------------------- Album Database Connection -------------------
album_db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="pandav91",
    database="snapsearch"
)
album_cursor = album_db.cursor()

# Create albums table if it doesn't exist
album_cursor.execute("""
    CREATE TABLE IF NOT EXISTS albums (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        album_name VARCHAR(255) NOT NULL,
        image_path VARCHAR(255) NOT NULL,
        image_data LONGBLOB NOT NULL
    )
""")
album_db.commit()

# ------------------- User Authentication Routes -------------------
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
            return jsonify({"error": "No face detected in the image"}), 400

        encoding_binary = pickle.dumps(face_encoding)

        new_user = Face(face_id=face_id, email=email, image_path=image_path, face_encoding=encoding_binary)
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('homepage'))

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
            return jsonify({"error": "Invalid email or password"}), 401

    return render_template("login.html")

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

# ------------------- Face Matching Routes -------------------
@app.route('/store-face', methods=['POST'])
def store_face():
    if 'image' not in request.files or 'face_id' not in request.form or 'email' not in request.form or 'password' not in request.form:
        return jsonify({"error": "Image, Face ID, Email, and Password are required"}), 400

    image = request.files['image']
    face_id = request.form['face_id']
    email = request.form['email']
    password = request.form['password']

    if Face.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    image_filename = f"{face_id}.jpg"
    image_path = os.path.join(UPLOAD_FOLDER, image_filename)
    image.save(image_path)

    face_encoding = convert_image_to_face_id(image_path, image.filename)
    if face_encoding is None:
        return jsonify({"error": "No face detected in the image"}), 400

    encoding_binary = pickle.dumps(face_encoding)

    new_user = Face(face_id=face_id, email=email, image_path=image_path, face_encoding=encoding_binary)
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    return redirect(url_for('homepage'))

@app.route('/get-faces', methods=['GET'])
def get_faces():
    faces = Face.query.all()
    face_data = [{"face_id": face.face_id, "image_path": face.image_path} for face in faces]
    return jsonify(face_data)

@app.route('/images/<filename>')
def get_image(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ------------------- Album Routes -------------------
@app.route("/upload_album", methods=["POST"])
def upload_album():
    print("Received Request!")  # Debugging step

    if 'images' not in request.files:
        print("No 'images' in request.files")  # Debugging step
        return "No images uploaded", 400  

    files = request.files.getlist('images')
    print(f"Files received: {[file.filename for file in files]}")  # Debugging step

    if not files or files[0].filename == '':
        print("No files selected")  # Debugging step
        return "No selected file", 400  

    # Check if album_id exists
    album_id = request.form.get('album_id')  # Ensure the album_id is retrieved correctly
    if not album_id:
        print("Album ID is missing!")  # Debugging step
        return "Album ID is required", 400  

    # Use album_id, not album_name
    album_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'uploads', str(album_id))
    os.makedirs(album_folder, exist_ok=True)

    for file in files:
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file_path = os.path.join(album_folder, filename)
            file.save(file_path)
            print(f"Saved: {file_path}")  # Debugging step

            # Store in DB
            with open(file_path, "rb") as f:
                image_blob = f.read()
            
            album_cursor.execute("INSERT INTO albums (user_id, album_id, image_path, image_data) VALUES (%s, %s, %s, %s)", 
                                 (session.get('user_id'), album_id, file_path, image_blob))
            album_db.commit()

    return redirect(url_for("homepage"))


@app.route("/create-album", methods=["GET", "POST"])
def create_album_page():
    if request.method == "POST":
        return upload_album()  # This will call your upload_album function
    return render_template("create_album.html")  # This will show the create album form when the method is GET

@app.route('/view-albums')
def view_albums():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, name FROM albums WHERE user_id = %s", (session["user_id"],))
    albums = cursor.fetchall()
    cursor.close()
    
    return render_template("view_albums.html", albums=albums)


    
@app.route('/images/uploads/<album_name>/<filename>')
def get_album_image(album_name, filename):
    # Define the root upload folder path
    album_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'uploads', album_name)
    
    # Ensure the file exists in the album folder
    image_path = os.path.join(album_folder, filename)
    if os.path.exists(image_path):
        return send_from_directory(album_folder, filename)
    else:
        return jsonify({"error": "Image not found"}), 404
    
@app.route('/my-albums')
def my_albums():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session['user_id']
    album_cursor.execute("SELECT id, album_name FROM albums WHERE user_id = %s", (user_id,))
    albums = [{"id": row[0], "name": row[1]} for row in album_cursor.fetchall()]

    return jsonify({"albums": albums})

@app.route('/join-album/<int:album_id>')
def join_album_page(album_id):
    # Process the joining logic using album_id
    return f"Joining album with ID {album_id}"

# ------------------- Homepage Route -------------------
@app.route('/homepage')
def homepage():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Fetch available albums
    album_cursor.execute("SELECT id, album_name FROM albums")
    albums = album_cursor.fetchall()  # List of (id, name)

    return render_template("homepage.html", albums=albums)

@app.route("/")
def home():
    return render_template("index.html")  # Show a page with both Sign Up and Login options


# ------------------- Run Flask Server -------------------

if __name__ == "__main__":
    app.run(debug=False, port=5002)  # Change debug to False
