from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for
import os
import pickle
import bcrypt
from flask_sqlalchemy import SQLAlchemy
from image_handler import convert_image_to_face_id  # Ensure this file exists

# Initialize Flask app
app = Flask(__name__)

# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+mysqlconnector://root:pandav91@localhost/face_matching"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  

# Initialize database
db = SQLAlchemy(app)

# 🟢 Define Face model
class Face(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    face_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False) 
    password = db.Column(db.String(255), nullable=False)  
    face_encoding = db.Column(db.LargeBinary, nullable=True)  # ✅ Allow NULL
    image_path = db.Column(db.String(255), nullable=True)

# Create tables
with app.app_context():
    db.create_all()

# Image upload folder
UPLOAD_FOLDER = 'images'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 🟢 Landing Page (Sign In / Sign Up)
@app.route("/")
def home():
    return render_template("index.html")

# 🟢 Signup Route
@app.route("/signup", methods=["GET", "POST"])
def signup_page():
    if request.method == "POST":
        data = request.json
        email = data.get("email")
        password = data.get("password")

        # Check if the user already exists
        existing_user = Face.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({"error": "Email already exists!"}), 400

        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Create a new user without face_encoding
        new_user = Face(face_id=email, email=email, password=hashed_password, face_encoding=None, image_path=None)
        db.session.add(new_user)
        db.session.commit()

        # Redirect to the upload face page
        return jsonify({"message": "Signup successful! Please upload your face.", "redirect": f"/upload-face/{email}"}), 201
    
    return render_template("signup.html")  # Show signup form if GET request

# 🟢 Face Upload Page
@app.route('/upload-face/<face_id>', methods=['GET', 'POST'])
def upload_face_page(face_id):
    if request.method == 'POST':
        if 'image' not in request.files:
            return jsonify({"error": "No image uploaded"}), 400
        
        image = request.files['image']
        image_path = os.path.join(UPLOAD_FOLDER, f"{face_id}.jpg")
        image.save(image_path)

        # Convert image to face encoding
        face_encoding = convert_image_to_face_id(image_path, image.filename)
        if face_encoding is None:
            return jsonify({"error": "No face detected in the image"}), 400
        
        encoding_binary = pickle.dumps(face_encoding)

        # Update database with face encoding
        user = Face.query.filter_by(face_id=face_id).first()
        if user:
            user.face_encoding = encoding_binary
            user.image_path = image_path
            db.session.commit()

            return jsonify({"message": "Face uploaded successfully!", "redirect": "/login"}), 200
    
    return render_template('upload_face.html', face_id=face_id)

# 🟢 Login Route
@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")

        user = Face.query.filter_by(email=email).first()
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
            return jsonify({"message": "Login successful", "redirect": "/dashboard", "face_id": user.face_id})
        else:
            return jsonify({"error": "Invalid email or password"}), 401

    return render_template("login.html")  # Renders login form for GET request

# 🟢 Dashboard (After Login)
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

# 🟢 Serve Uploaded Images
@app.route('/images/<filename>')
def get_image(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# Run Flask App
if __name__ == '__main__':  
    app.run(debug=True, port=5002)
