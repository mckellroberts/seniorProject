import requests, os
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from rag.ingestDocs import ingestForUser, SUPPORTED_EXTENSIONS
from rag.tools.vectorStore import ChromaRetriever
from rag.agent import generateInUserVoice

app = Flask(__name__)
CORS(app)

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR         = Path(__file__).parent
UPLOAD_FOLDER    = BASE_DIR / "rag" / "data" / "raw"
VECTOR_STORE_DIR = BASE_DIR / "rag" / "data" / "vector_store"

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = SUPPORTED_EXTENSIONS  # {".pdf", ".txt", ".md", ".docx"}



# ── Helpers ────────────────────────────────────────────────────────────────────

def allowedFile(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS

def getUserId(req) -> str:
    """
    Placeholder — swap this out for real auth later.
    Accepts user_id from form data, JSON body, or falls back to 'default'.
    """
    return (
        req.form.get("user_id")
        or (req.json or {}).get("user_id")
        or "default"
    )


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/upload", methods=["POST"])
def uploadFile():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    if not allowedFile(file.filename):
        return jsonify({
            "error": f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        }), 400

    userId = getUserId(request)

    # Save raw file
    savePath = UPLOAD_FOLDER / file.filename
    file.save(savePath)

    # Ingest into user's personal vector store
    try:
        summary = ingestForUser(
            filePath=savePath,
            userId=userId,
            vectorStoreDir=VECTOR_STORE_DIR,
        )
    except Exception as e:
        return jsonify({"error": f"Ingestion failed: {str(e)}"}), 500

    return jsonify({
        "message": "File uploaded and ingested successfully.",
        **summary,
    })


@app.route("/sources", methods=["GET"])
def listSources():
    """List all files ingested for a user."""
    userId = request.args.get("user_id", "default")
    retriever = ChromaRetriever(
        persistDirectory=VECTOR_STORE_DIR,
        userId=userId,
    )
    return jsonify({
        "userId": userId,
        "sources": retriever.listSources(),
        "totalChunks": retriever.count(),
    })


@app.route("/sources/<filename>", methods=["DELETE"])
def deleteSource(filename):
    """Remove a specific uploaded work from the vector store."""
    userId = request.args.get("userId", "default")
    retriever = ChromaRetriever(
        persistDirectory=VECTOR_STORE_DIR,
        userId=userId,
    )
    removed = retriever.deleteSource(filename)
    return jsonify({"deleted_chunks": removed, "file": filename})


@app.route("/generate", methods=["POST"])
def generate():
    """Generate text in the user's writing voice."""
    data = request.json or {}

    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    userId    = data.get("userId", "default")
    styleHint = data.get("styleHint", "")

    try:
        result = generateInUserVoice(
            prompt=prompt,
            userId=userId,
            vectorStoreDir=VECTOR_STORE_DIR,
            styleHint=styleHint,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if "error" in result and not result.get("generatedText"):
        return jsonify(result), 400

    return jsonify(result)


@app.route("/styleProfile", methods=["GET"])
def style_profile():
    """Return a summary of the user's detected writing style."""
    from rag.agent import buildStyleProfile
    userId = request.args.get("userId", "default")
    retriever = ChromaRetriever(
        persistDirectory=VECTOR_STORE_DIR,
        userId=userId,
    )
    if retriever.count() == 0:
        return jsonify({"error": "No writing samples uploaded yet."}), 400

    profile = buildStyleProfile(retriever)
    return jsonify({"userId": userId, "styleProfile": profile})


if __name__ == "__main__":
    app.run(debug=True)