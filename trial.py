import face_recognition
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/compare_faces', methods=['POST'])
def compare_faces():
    try:
        # Get the image files from the request
        image_1_file = request.files['image_1']
        image_2_file = request.files['image_2']
        
        # Load the images and get the face encodings
        image_1 = face_recognition.load_image_file(image_1_file)
        image_2 = face_recognition.load_image_file(image_2_file)

        # Get the face encodings for both images
        image_1_encoding = face_recognition.face_encodings(image_1)

        # Check if at least one face is detected in image-1
        if len(image_1_encoding) == 0:
            return jsonify({'status': 'no faces detected in image-1'}), 400

        image_2_encodings = face_recognition.face_encodings(image_2)

        # Check if faces are detected in image-2
        if len(image_2_encodings) == 0:
            return jsonify({'status': 'no faces detected in image-2'}), 400

        matches = []

        # Compare the face from image-1 with each face in image-2
        for face_encoding in image_2_encodings:
            match = face_recognition.compare_faces([image_1_encoding[0]], face_encoding)
            if match[0]:
                matches.append(True)
            else:
                matches.append(False)

        # Check if any match is found
        if any(matches):
            return jsonify({'status': 'match found'})
        else:
            return jsonify({'status': 'no match found'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
