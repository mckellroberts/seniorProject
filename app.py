import requests, os

from flask import Flask, request, jsonify

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return jsonify({'status': 'API running'})

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    return jsonify({"message": "File uploaded"})


# -------- Text generation --------
@app.route('/generate', methods=['POST'])
def generate_text():
    data = request.json or {}

    prompt = data.get('prompt', '')
    user_style = data.get('style_context', '')

    response = requests.post(
        'http://localhost:11434/api/generate',
        json={
            'model': 'llama3.2',
            'prompt': prompt,
            'system': f"Write in this style: {user_style}"
        }
    )

    return jsonify(response.json())

if __name__ == '__main__':
    app.run(debug=True)
