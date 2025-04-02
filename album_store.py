import os
import mysql.connector
from flask import Flask, request, jsonify, send_file, render_template, session
import io
from flask import redirect, url_for


app = Flask(__name__)
app.secret_key = "1212"  # Set a secret key for session management

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

@app.route("/set-session")
def set_session():
    session['user_id'] = 1  # Set a test user ID
    return "Session set!"


@app.route("/upload-album", methods=["POST"])
def upload_album():
    user_id = session['user_id']
    album_name = request.form.get("album_name")
    files = request.files.getlist("images")

    if not album_name or len(files) == 0:
        return jsonify({"error": "Missing album name or images"}), 400

    # Loop through each file and save it
    for file in files:
        try:
            # Save the image as a file on the disk
            image_filename = f"{album_name}_{file.filename}"
            image_path = os.path.join(UPLOAD_FOLDER, image_filename)

            # Save the file to disk
            file.save(image_path)  # Directly save the image file

            # Read the file as binary for database insertion
            with open(image_path, 'rb') as img_file:
                image_binary = img_file.read()

            # Insert image data into the database
            album_cursor.execute(
                "INSERT INTO albums (user_id, album_name, image_data, image_path) VALUES (%s, %s, %s, %s)",
                (user_id, album_name, image_binary, image_path),
            )
            album_db.commit()

        except Exception as e:
            return jsonify({"error": f"Error uploading image: {e}"}), 500

    return redirect(url_for('view_album', album_name=album_name))


@app.route("/get-image/<int:image_id>")
def get_image(image_id):
    cursor.execute("SELECT image_data FROM albums WHERE id = %s", (image_id,))
    image_data = cursor.fetchone()

    if image_data:
        return send_file(io.BytesIO(image_data[0]), mimetype="image/jpeg")
    else:
        return jsonify({"error": "Image not found"}), 404

@app.route("/view-album/<album_name>")
def view_album(album_name):
    cursor.execute("SELECT id FROM albums WHERE album_name = %s", (album_name,))
    images = cursor.fetchall()

    image_urls = [f"/get-image/{image[0]}" for image in images]  # Convert IDs to image URLs

    return render_template("gallery.html", album_name=album_name, image_urls=image_urls)


@app.route("/create-album", methods=["GET", "POST"])
def create_album_page():
    if request.method == "POST":
        return upload_album()
    return render_template("create_album.html")


if __name__ == "__main__":
    app.run(debug=False, port=5003)  # Change debug to False