import face_recognition
import cv2
import numpy as np
import os

# Load known faces from a directory
def load_known_faces(known_faces_dir="known_faces"):
    known_face_encodings = []
    known_face_names = []

    if not os.path.exists(known_faces_dir):
        print(f"Directory '{known_faces_dir}' does not exist!")
        return known_face_encodings, known_face_names

    for filename in os.listdir(known_faces_dir):
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            image_path = os.path.join(known_faces_dir, filename)
            image = load_and_resize_image(image_path)  # Use resized image
            encodings = face_recognition.face_encodings(image)

            if len(encodings) == 0:
                print(f"Warning: No face found in {filename}")
                continue
            elif len(encodings) > 1:
                print(f"Warning: Multiple faces detected in {filename}, using the first one.")

            known_face_encodings.append(encodings[0])
            known_face_names.append(os.path.splitext(filename)[0])

    return known_face_encodings, known_face_names

# Function to load and resize an image
def load_and_resize_image(image_path):
    image = face_recognition.load_image_file(image_path)
    image = cv2.resize(image, (500, 500))  # Resize to 500x500 for better detection
    return image

# Compare a new face with known faces
def compare_faces(known_face_encodings, known_face_names, new_image_path):
    new_image = load_and_resize_image(new_image_path)
    new_face_encodings = face_recognition.face_encodings(new_image)

    if len(new_face_encodings) == 0:
        print("⚠ No faces found in the new image!")
        return None

    for new_face_encoding in new_face_encodings:
        matches = face_recognition.compare_faces(known_face_encodings, new_face_encoding)
        if True in matches:
            first_match_index = matches.index(True)
            return known_face_names[first_match_index]
    
    return None

# Convert an image to a face ID
def convert_image_to_face_id(image_path, file_name):
    if not file_name.lower().endswith((".jpg", ".jpeg", ".png")):
        print("❌ Invalid file format")
        return None
    
    image = load_and_resize_image(image_path)
    encodings = face_recognition.face_encodings(image)

    if len(encodings) == 0:
        print(f"⚠ Warning: No face found in {file_name}")
        return None
    elif len(encodings) > 1:
        print(f"⚠ Warning: Multiple faces detected in {file_name}, using the first one.")
    
    return encodings[0]

# Compare two images
def compare_faces(image1_path, image2_path):
    image1 = load_and_resize_image(image1_path)
    image2 = load_and_resize_image(image2_path)

    encodings1 = face_recognition.face_encodings(image1)
    encodings2 = face_recognition.face_encodings(image2)

    print(f"Encodings1: {encodings1}")  # Debugging
    print(f"Encodings2: {encodings2}")  # Debugging

    if len(encodings1) == 0 or len(encodings2) == 0:
        print("⚠ No faces found in one or both images!")
        return False

    match = face_recognition.compare_faces([encodings1[0]], encodings2[0])[0]

    return match
