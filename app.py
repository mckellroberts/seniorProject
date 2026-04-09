import requests, os, subprocess, time, secrets
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, redirect, url_for
from flask_cors import CORS
from flask_login import LoginManager, login_required, current_user

from rag.tools.ingestDocs import ingestForUser, SUPPORTED_EXTENSIONS
from rag.tools.vectorStore import ChromaRetriever
from rag.agents.agent import (
    generateInUserVoice,
    getWritingIdeas,
    continueWriting,
    getUnstuck,
    writeScene,
    writeDialogue,
)
from auth import auth, initDb, loadUser

app = Flask(__name__)
CORS(app)

# ── Secret key ─────────────────────────────────────────────────────────────────
# Reads SECRET_KEY from the environment (set this in production).
# Locally, falls back to a .secret_key file so the key survives restarts.
_SECRET_FILE = Path(__file__).parent / ".secret_key"

def _loadSecretKey() -> str:
    key = os.environ.get("SECRET_KEY")
    if key:
        return key
    if _SECRET_FILE.exists():
        return _SECRET_FILE.read_text().strip()
    key = secrets.token_hex(32)
    _SECRET_FILE.write_text(key)
    print("Generated new secret key → .secret_key  (set SECRET_KEY env var in production)")
    return key

app.config["SECRET_KEY"] = _loadSecretKey()
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# ── Flask-Login ────────────────────────────────────────────────────────────────
loginManager = LoginManager(app)

@loginManager.user_loader
def userLoader(userId):
    return loadUser(int(userId))

@loginManager.unauthorized_handler
def unauthorized():
    # API requests get a 401; browser navigations get redirected to /login
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        return jsonify({"error": "Not authenticated"}), 401
    return redirect("/login")

# ── Auth blueprint ─────────────────────────────────────────────────────────────
app.register_blueprint(auth)
initDb()

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR         = Path(__file__).parent
UPLOAD_FOLDER    = BASE_DIR / "rag" / "data" / "raw"
VECTOR_STORE_DIR = BASE_DIR / "rag" / "data" / "vectorStore"

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)

# ── Ollama ─────────────────────────────────────────────────────────────────────

def _ollamaRunning() -> bool:
    try:
        return requests.get("http://localhost:11434", timeout=2).status_code == 200
    except requests.RequestException:
        return False

def ensureOllama() -> None:
    if _ollamaRunning():
        print("Ollama already running.")
        return

    print("Starting Ollama...")
    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for _ in range(20):
        time.sleep(1)
        if _ollamaRunning():
            print("Ollama started.")
            return

    print("Warning: Ollama did not respond after 20 seconds. Generation may fail.")

ensureOllama()

ALLOWED_EXTENSIONS = SUPPORTED_EXTENSIONS  # {".pdf", ".txt", ".md", ".docx"}



# ── Helpers ────────────────────────────────────────────────────────────────────

def allowedFile(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS

def getUserId(req) -> str:
    try:
        json_body = req.get_json(silent=True) or {}
    except Exception:
        json_body = {}

    return (
        req.form.get("user_id")
        or json_body.get("user_id")
        or "default"
    )


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/login")
def loginPage():
    return send_from_directory(".", "login.html")

@app.route("/")
@login_required
def home():
    return send_from_directory(".", "index.html")

@app.route("/ideas", methods=["GET"])
@login_required
def writingIdeas():
    """Return story/writing ideas tailored to the user's style."""
    userId = str(current_user.id)
    topic  = request.args.get("topic", "")
    count  = int(request.args.get("count", 5))

    result = getWritingIdeas(
        userId=userId,
        vectorStoreDir=VECTOR_STORE_DIR,
        topic=topic,
        count=count,
    )

    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)

@app.route("/upload", methods=["POST"])
@login_required
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

    userId = str(current_user.id)

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
@login_required
def listSources():
    """List all files ingested for a user."""
    userId = str(current_user.id)
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
@login_required
def deleteSource(filename):
    """Remove a specific uploaded work from the vector store."""
    userId = str(current_user.id)
    retriever = ChromaRetriever(
        persistDirectory=VECTOR_STORE_DIR,
        userId=userId,
    )
    removed = retriever.deleteSource(filename)
    return jsonify({"deleted_chunks": removed, "file": filename})


@app.route("/generate", methods=["POST"])
@login_required
def generate():
    """Generate text in the user's writing voice."""
    data = request.json or {}

    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    userId    = str(current_user.id)
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
@login_required
def styleProfile():
    """Return a summary of the user's detected writing style."""
    from rag.agents.agent import buildStyleProfile
    userId = str(current_user.id)
    retriever = ChromaRetriever(
        persistDirectory=VECTOR_STORE_DIR,
        userId=userId,
    )
    if retriever.count() == 0:
        return jsonify({"error": "No writing samples uploaded yet."}), 400

    profile = buildStyleProfile(retriever, userId=userId, vectorStoreDir=VECTOR_STORE_DIR)
    return jsonify({"userId": userId, "styleProfile": profile})


@app.route("/continue", methods=["POST"])
@login_required
def continueStory():
    """Continue the story from the writer's last paragraph."""
    data = request.json or {}

    lastParagraph = data.get("lastParagraph", "").strip()
    if not lastParagraph:
        return jsonify({"error": "lastParagraph is required"}), 400

    userId = str(current_user.id)

    try:
        result = continueWriting(
            lastParagraph=lastParagraph,
            userId=userId,
            vectorStoreDir=VECTOR_STORE_DIR,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)


@app.route("/unstuck", methods=["POST"])
@login_required
def unstuck():
    """Return story-grounded suggestions when the writer is stuck."""
    data = request.json or {}

    userId  = str(current_user.id)
    context = data.get("context", "").strip()
    count   = int(data.get("count", 3))

    try:
        result = getUnstuck(
            userId=userId,
            vectorStoreDir=VECTOR_STORE_DIR,
            context=context,
            count=count,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)


@app.route("/scene", methods=["POST"])
@login_required
def scene():
    """Draft a scene with specific parameters in the author's voice."""
    data = request.json or {}

    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    userId     = str(current_user.id)
    characters = data.get("characters", [])   # list of character name strings
    location   = data.get("location", "").strip()
    mood       = data.get("mood", "").strip()

    try:
        result = writeScene(
            prompt=prompt,
            userId=userId,
            vectorStoreDir=VECTOR_STORE_DIR,
            characters=characters or None,
            location=location,
            mood=mood,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)


@app.route("/dialogue", methods=["POST"])
@login_required
def dialogue():
    """Write dialogue between specific characters in the author's voice."""
    data = request.json or {}

    context = data.get("context", "").strip()
    if not context:
        return jsonify({"error": "context is required"}), 400

    userId     = str(current_user.id)
    characters = data.get("characters", [])   # list of character name strings

    try:
        result = writeDialogue(
            context=context,
            userId=userId,
            vectorStoreDir=VECTOR_STORE_DIR,
            characters=characters or None,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)