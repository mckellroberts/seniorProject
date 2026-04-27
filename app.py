import json, requests, os, subprocess, time, secrets, sqlite3
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, Response, stream_with_context
from flask_cors import CORS
from flask_login import LoginManager, login_required, current_user

from rag.tools.ingestDocs import ingestForUser, SUPPORTED_EXTENSIONS
from rag.tools.vectorStore import ChromaRetriever
from rag.agents.agent import (
    generateInUserVoice,
    streamInUserVoice,
    getWritingIdeas,
    continueWriting,
    getUnstuck,
    writeScene,
    writeDialogue,
)
from auth import auth, initDb, loadUser, DB_PATH

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
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

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
BASE_DIR              = Path(__file__).parent
UPLOAD_FOLDER         = BASE_DIR / "rag" / "data" / "raw"
VECTOR_STORE_DIR      = BASE_DIR / "rag" / "data" / "vectorStore"
DEMO_VECTOR_STORE_DIR = BASE_DIR / "rag" / "data" / "demo" / "vectorStore"

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
DEMO_VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)

# ── Ollama ─────────────────────────────────────────────────────────────────────

def _ollamaRunning() -> bool:
    try:
        return requests.get("http://localhost:11434", timeout=5).status_code == 200
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


def _overridePath(userId: str) -> Path:
    return BASE_DIR / "rag" / "data" / "cache" / f"{userId}_style_override.json"


def _loadOverride(userId: str) -> dict:
    p = _overridePath(userId)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {}


def _saveOverride(userId: str, override: dict) -> None:
    _overridePath(userId).write_text(json.dumps(override, indent=2))


def _mergeProfile(base: dict, override: dict) -> dict:
    merged = {}
    for section in ("sentences", "vocabulary", "tone"):
        merged[section] = {**base.get(section, {}), **override.get(section, {})}
    return merged


def _overrideToHint(override: dict) -> str:
    labels = {
        "sentences":  {"rhythm": "Sentence rhythm", "complexity": "Sentence complexity",
                       "fragmentUse": "Fragment use", "patterns": "Structural patterns"},
        "vocabulary": {"register": "Vocabulary register", "complexity": "Word complexity",
                       "petWords": "Pet words and diction", "avoidances": "Avoidances"},
        "tone":       {"primaryTone": "Primary tone", "toneRange": "Tone range",
                       "emotionalDepth": "Emotional depth", "atmosphericWords": "Atmospheric words",
                       "toneShifts": "Tone shifts"},
    }
    lines = []
    for section, fields in labels.items():
        for field, label in fields.items():
            val = override.get(section, {}).get(field, "")
            if val:
                lines.append(f"{label}: {val}")
    if not lines:
        return ""
    return "PROFILE OVERRIDES (use these instead of analyzed values):\n" + "\n".join(lines)

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

def _getDb():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/login")
def loginPage():
    return send_from_directory(".", "login.html")

@app.route("/")
@login_required
def home():
    return send_from_directory(".", "index.html")

@app.route("/ideas-page")
@login_required
def ideasPage():
    return send_from_directory(".", "ideas.html")

@app.route("/ideas", methods=["GET"])
@login_required
def writingIdeas():
    """Generate ideas and persist them for the current user."""
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

    ideas = result.get("ideas", [])
    saved = []
    with _getDb() as conn:
        for idea in ideas:
            cursor = conn.execute(
                "INSERT INTO saved_ideas (user_id, idea, hook, fit, topic) VALUES (?, ?, ?, ?, ?)",
                (current_user.id, idea.get("idea", ""), idea.get("hook", ""), idea.get("fit", ""), topic),
            )
            saved.append({**idea, "id": cursor.lastrowid})

    return jsonify({**result, "ideas": saved})


@app.route("/ideas/history", methods=["GET"])
@login_required
def ideasHistory():
    """Return all previously saved ideas for the current user."""
    with _getDb() as conn:
        rows = conn.execute(
            "SELECT id, idea, hook, fit, topic, created_at FROM saved_ideas WHERE user_id = ? ORDER BY created_at DESC",
            (current_user.id,),
        ).fetchall()
    return jsonify({"ideas": [dict(r) for r in rows]})


@app.route("/ideas/<int:ideaId>", methods=["DELETE"])
@login_required
def deleteIdea(ideaId):
    """Delete a saved idea belonging to the current user."""
    with _getDb() as conn:
        deleted = conn.execute(
            "DELETE FROM saved_ideas WHERE id = ? AND user_id = ?",
            (ideaId, current_user.id),
        ).rowcount
    if not deleted:
        return jsonify({"error": "Idea not found"}), 404
    return jsonify({"deleted": ideaId})

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

    overrideHint = _overrideToHint(_loadOverride(userId))
    if overrideHint:
        styleHint = overrideHint + ("\n\n" + styleHint if styleHint else "")

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


@app.route("/generate/stream", methods=["POST"])
@login_required
def generateStream():
    """Stream generated text chunk-by-chunk as Server-Sent Events."""
    data      = request.json or {}
    prompt    = data.get("prompt", "").strip()
    styleHint = data.get("styleHint", "")
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    userId = str(current_user.id)
    overrideHint = _overrideToHint(_loadOverride(userId))
    if overrideHint:
        styleHint = overrideHint + ("\n\n" + styleHint if styleHint else "")

    @stream_with_context
    def generate():
        for chunk in streamInUserVoice(prompt, userId, VECTOR_STORE_DIR, styleHint):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@app.route("/style-page")
@login_required
def stylePage():
    return send_from_directory(".", "style.html")


@app.route("/styleProfile", methods=["GET"])
@login_required
def styleProfile():
    """Return a full style breakdown, merged with any saved user overrides."""
    from rag.agents.agent import _getProfiles
    userId = str(current_user.id)
    retriever = ChromaRetriever(persistDirectory=VECTOR_STORE_DIR, userId=userId)
    if retriever.count() == 0:
        return jsonify({"error": "No writing samples uploaded yet."}), 400

    profile, storyPatterns, paragraphStats, characterProfiles, plotSummary, _, _ = \
        _getProfiles(retriever, userId, VECTOR_STORE_DIR)

    override = _loadOverride(userId)
    if override:
        profile = _mergeProfile(profile, override)

    return jsonify({
        "userId":            userId,
        "styleProfile":      profile,
        "paragraphStats":    paragraphStats,
        "storyPatterns":     storyPatterns,
        "characterProfiles": characterProfiles,
        "plotSummary":       plotSummary,
        "hasOverride":       bool(override),
    })


@app.route("/styleProfile", methods=["POST"])
@login_required
def saveStyleProfile():
    """Save user edits to the style profile."""
    data = request.json or {}
    override = data.get("styleProfile", {})
    if not override:
        return jsonify({"error": "No profile data provided"}), 400
    _saveOverride(str(current_user.id), override)
    return jsonify({"saved": True})


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


# ── Demo / Tester Routes ───────────────────────────────────────────────────────

@app.route("/demo/authors", methods=["GET"])
@login_required
def listDemoAuthors():
    """Return all demo authors with metadata and readiness status."""
    from rag.demo.authors import DEMO_AUTHORS
    result = []
    for key, author in DEMO_AUTHORS.items():
        retriever = ChromaRetriever(persistDirectory=DEMO_VECTOR_STORE_DIR, userId=f"demo_{key}")
        count = retriever.count()
        result.append({
            "key":        key,
            "name":       author["name"],
            "era":        author["era"],
            "style":      author["style"],
            "prompts":    author["prompts"],
            "ready":      count > 0,
            "chunkCount": count,
        })
    return jsonify({"authors": result})


@app.route("/demo/generate", methods=["POST"])
@login_required
def demoGenerate():
    """Generate text in a demo author's voice."""
    from rag.demo.authors import DEMO_AUTHORS
    data      = request.json or {}
    authorKey = data.get("authorKey", "").strip()
    prompt    = data.get("prompt", "").strip()

    if not authorKey or not prompt:
        return jsonify({"error": "authorKey and prompt are required"}), 400
    if authorKey not in DEMO_AUTHORS:
        return jsonify({"error": f"Unknown author key: {authorKey}"}), 400

    voiceInstructions = DEMO_AUTHORS[authorKey].get("voiceInstructions", "")

    try:
        result = generateInUserVoice(
            prompt=prompt,
            userId=f"demo_{authorKey}",
            vectorStoreDir=DEMO_VECTOR_STORE_DIR,
            styleHint=voiceInstructions,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if "error" in result and not result.get("generatedText"):
        return jsonify(result), 400

    return jsonify({
        **result,
        "authorKey":  authorKey,
        "authorName": DEMO_AUTHORS[authorKey]["name"],
    })


@app.route("/demo/generate/stream", methods=["POST"])
@login_required
def demoGenerateStream():
    """Stream demo generation as Server-Sent Events."""
    from rag.demo.authors import DEMO_AUTHORS
    data      = request.json or {}
    authorKey = data.get("authorKey", "").strip()
    prompt    = data.get("prompt", "").strip()

    if not authorKey or not prompt:
        return jsonify({"error": "authorKey and prompt are required"}), 400
    if authorKey not in DEMO_AUTHORS:
        return jsonify({"error": f"Unknown author key: {authorKey}"}), 400

    userId            = f"demo_{authorKey}"
    voiceInstructions = DEMO_AUTHORS[authorKey].get("voiceInstructions", "")

    @stream_with_context
    def generate():
        for chunk in streamInUserVoice(prompt, userId, DEMO_VECTOR_STORE_DIR, styleHint=voiceInstructions):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@app.route("/demo/unstuck", methods=["POST"])
@login_required
def demoUnstuck():
    """Get story suggestions in a demo author's voice."""
    from rag.demo.authors import DEMO_AUTHORS
    data      = request.json or {}
    authorKey = data.get("authorKey", "").strip()
    context   = data.get("context", "").strip()
    count     = int(data.get("count", 3))

    if not authorKey:
        return jsonify({"error": "authorKey is required"}), 400
    if authorKey not in DEMO_AUTHORS:
        return jsonify({"error": f"Unknown author key: {authorKey}"}), 400

    try:
        result = getUnstuck(
            userId=f"demo_{authorKey}",
            vectorStoreDir=DEMO_VECTOR_STORE_DIR,
            context=context,
            count=count,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if "error" in result:
        return jsonify(result), 400

    return jsonify({**result, "authorKey": authorKey})


if __name__ == "__main__":
    app.run(debug=True)