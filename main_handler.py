
from flask import Flask, request, jsonify,send_file
import os
import mysql.connector
from image_handler import compare_faces 






app = Flask(__name__)
UPLOAD_FOLDER = "images"  # Make sure this matches the folder where images are stored


# Database connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="pandav91",
    database="snapsearch"
)
cursor = db.cursor()

if db.is_connected():
    print("Database connected successfully!")
else:
    print("Database connection failed!")

@app.route('/match-face', methods=['POST'])
def match_face():
    data = request.get_json()
    if not data or 'face_id' not in data:
        return jsonify({"error": "Missing face_id"}), 400

    face_id = data['face_id']
    user_face_path = f"{UPLOAD_FOLDER}/{face_id}.jpg"  

    if not os.path.exists(user_face_path):
        return jsonify({"error": "Face ID not found"}), 404

    if not db.is_connected():
        return jsonify({"error": "Database connection lost"}), 500

    cursor.execute("SELECT id, image_data FROM albums")  
    images = cursor.fetchall()

    matched_images = []

    for image_id, image_blob in images:
        temp_image_path = f"temp_image_{image_id}.jpg"

        # Save BLOB image as a temporary file for comparison
        with open(temp_image_path, "wb") as file:
            file.write(image_blob)

        if compare_faces(user_face_path, temp_image_path):
            image_url = f"http://127.0.0.1:5001/get-image/{image_id}"
            matched_images.append(image_url)  # 🔹 Append URL instead of ID

        os.remove(temp_image_path)  # Cleanup

    if not matched_images:
        return jsonify({"message": "No matching faces found"}), 404

    return jsonify({"matched_images": matched_images})  # 🔹 Returns URLs instead of IDs


@app.route('/get-image/<int:image_id>', methods=['GET'])
def get_image(image_id):
    cursor.execute("SELECT image_data FROM albums WHERE id = %s", (image_id,))
    result = cursor.fetchone()

    if not result:
        return jsonify({"error": "Image not found"}), 404

    image_path = f"temp_image_{image_id}.jpg"

    # Save BLOB image as a temporary file
    with open(image_path, "wb") as file:
        file.write(result[0])

    return send_file(image_path, mimetype="image/jpeg")

if __name__ == '__main__':
    app.run(debug=True, port=5004)
