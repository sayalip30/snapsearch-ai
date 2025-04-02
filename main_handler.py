import MySQLdb  # Correct import for mysqlclient
import os
from flask import Flask, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from image_store import Face, db, compare_faces  # Import compare_faces from image_store instead of image_handler
from PIL import Image
import face_recognition
from sqlalchemy import text  # Import text() for raw SQL queries

app = Flask(__name__)
UPLOAD_FOLDER = "images"  # Ensure this matches the folder where images are stored

# Configure your app with the database URI
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:pandav91@localhost/face_matching'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the SQLAlchemy instance
db.init_app(app)

# Database connection for album images
album_db = MySQLdb.connect(
    host="localhost",
    user="root",
    password="pandav91",
    database="snapsearch"
)
album_cursor = album_db.cursor()

# Function to get face encoding from an image path
def get_face_encoding(image_path):
    try:
        image = face_recognition.load_image_file(image_path)
        face_encodings = face_recognition.face_encodings(image)
        if len(face_encodings) > 0:
            return face_encodings[0]  # Return the encoding for the first face
        else:
            print(f"No face found in image: {image_path}")
            return None
    except Exception as e:
        print(f"Error processing image {image_path}: {e}")
        return None

# Endpoint to match faces
@app.route('/match-face', methods=['POST'])
def match_face():
    data = request.get_json()  # Decode the incoming JSON
    if not data or 'face_id' not in data:
        return jsonify({"error": "Missing face_id"}), 400

    face_id = data['face_id']
    print(f"Received face_id: {face_id}")

    user = Face.query.filter_by(face_id=face_id).first()
    if not user:
        print("User not found in database")
        return jsonify({"error": "User not found"}), 404
    
    print(f"User found: {user}, Image Path: {user.image_path}")

    user_face_encoding = get_face_encoding(user.image_path)
    if user_face_encoding is None:
        return jsonify({"error": "Unable to process user face image"}), 400

    print(f"User face encoding: {user_face_encoding}")  # Debugging line

    matched_images = []
    album_cursor.execute("SELECT id, image_data FROM albums")
    images = album_cursor.fetchall()

    for image_id, image_blob in images:
        temp_image_path = f"temp_image_{image_id}.jpg"
        print(f"Saving BLOB to: {temp_image_path}")
        with open(temp_image_path, "wb") as file:
            file.write(image_blob)

        try:
            with Image.open(temp_image_path) as img:
                img.verify()
            print(f"Verified image: {temp_image_path}")
        except Exception as e:
            print(f"Error with image {temp_image_path}: {e}")
            os.remove(temp_image_path)
            continue

        album_face_encoding = get_face_encoding(temp_image_path)
        if album_face_encoding is None:
            os.remove(temp_image_path)
            continue

        print(f"Comparing user face encoding with album face encoding")  # Debugging line
        match = compare_faces(user_face_encoding, album_face_encoding)
        if match:
            print(f"Match found for image_id {image_id}")
            image_url = f"http://127.0.0.1:5001/get-image/{image_id}"
            matched_images.append(image_url)

        os.remove(temp_image_path)

    if not matched_images:
        return jsonify({"message": "No matching faces found"}), 404

    return jsonify({"matched_images": matched_images})


# Endpoint to retrieve images by ID from album_store.py
@app.route('/get-image/<int:image_id>', methods=['GET'])
def get_image(image_id):
    album_cursor.execute("SELECT image_data FROM albums WHERE id = %s", (image_id,))
    result = album_cursor.fetchone()

    if not result:
        return jsonify({"error": "Image not found"}), 404

    image_blob = result[0]
    image_path = f"temp_image_{image_id}.jpg"

    # Write BLOB data to a file
    with open(image_path, "wb") as file:
        file.write(image_blob)

    try:
        with Image.open(image_path) as img:
            img.verify()  # Verify the image format
        return send_file(image_path, mimetype="image/jpeg")
    except Exception as e:
        os.remove(image_path)  # Clean up the corrupted file
        return jsonify({"error": f"Error with image file: {e}"}), 500




@app.route('/test-db', methods=['GET'])
def test_db():
    try:
        result = db.session.execute(text("SELECT COUNT(*) FROM face")).fetchone()
        return jsonify({"message": f"Database is working, total faces: {result[0]}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create all tables if they do not exist
    app.run(debug=True, port=5004)
