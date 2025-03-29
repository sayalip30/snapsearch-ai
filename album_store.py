import mysql.connector
from flask import Flask, request, jsonify
import os
from flask import send_file
import io

app = Flask(__name__)

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


# Create table for albums (storing images as BLOB)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS albums (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        album_name VARCHAR(255) NOT NULL,
        image_data LONGBLOB NOT NULL
    )
""")
db.commit()

@app.route("/upload-album", methods=["POST"])
def upload_album():
    user_id = request.form.get("user_id")
    album_name = request.form.get("album_name")
    files = request.files.getlist("images")  # Get multiple images

    print(f"Received user_id: {user_id}, album_name: {album_name}, total files: {len(files)}")

    if not user_id or not album_name or len(files) == 0:
        return jsonify({"error": "Missing data"}), 400

    for file in files:
        image_binary = file.read()  # Convert image to binary
        print(f"Saving file: {file.filename}, Size: {len(image_binary)} bytes")

        try:
            cursor.execute(
                "INSERT INTO albums (user_id, album_name, image_data) VALUES (%s, %s, %s)",
                (user_id, album_name, image_binary),
            )
            db.commit()
            print("Image inserted successfully!")
        except mysql.connector.Error as err:
            print(f"Database error: {err}")

    return jsonify({"message": "Images uploaded successfully!"})


@app.route("/get-image/<int:image_id>", methods=["GET"])
def get_image(image_id):
    cursor.execute("SELECT image_data FROM albums WHERE id = %s", (image_id,))
    image_data = cursor.fetchone()

    if image_data:
        return send_file(io.BytesIO(image_data[0]), mimetype="image/jpeg")
    else:
        return jsonify({"error": "Image not found"}), 404

if __name__ == "__main__":
    app.run(debug=True, port=5003)
