import os
import uuid
import json
import pickle
from datetime import datetime, timezone

from flask import Flask, Response, jsonify, render_template, request, session
from werkzeug.utils import secure_filename

from embedding import EMBED_MODEL_NAME, embed_chunks, model
from llm import DEFAULT_MODEL, ask_llm, get_available_models
from ollama_client import ollama_base_url, ollama_server_reachable
from pdf_utils import chunk_text, extract_from_pdf_bytes
from vector_store import create_index, search

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-change-me-in-production")

# ====================== Persistence Setup ======================
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def save_store(sid: str, store: dict):
    """Save store data to disk"""
    try:
        # Save metadata and chat history
        store_path = os.path.join(DATA_DIR, f"{sid}.json")
        save_data = {
            "doc_meta": store.get("doc_meta"),
            "chat_history": store.get("chat_history", []),
            "retrieval_k": store.get("retrieval_k", 5),
            "selected_model": store.get("selected_model", DEFAULT_MODEL),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        with open(store_path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)

        # Save FAISS index
        if store.get("index") is not None:
            index_path = os.path.join(DATA_DIR, f"{sid}_index.faiss")
            with open(index_path, "wb") as f:
                pickle.dump(store["index"], f)
    except Exception as e:
        print(f"Warning: Could not save data: {e}")


def load_store(sid: str) -> dict:
    """Load store data from disk"""
    store = {
        "index": None,
        "chunks": None,
        "chat_history": [],
        "last_query": "",
        "doc_meta": None,
        "retrieval_k": 5,
        "selected_model": DEFAULT_MODEL,
    }

    try:
        store_path = os.path.join(DATA_DIR, f"{sid}.json")
        if os.path.exists(store_path):
            with open(store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                store.update({k: v for k, v in data.items() if k in store})

        # Load FAISS index
        index_path = os.path.join(DATA_DIR, f"{sid}_index.faiss")
        if os.path.exists(index_path):
            with open(index_path, "rb") as f:
                store["index"] = pickle.load(f)
    except Exception as e:
        print(f"Warning: Could not load data: {e}")

    return store


# ====================== Flask Setup ======================
stores: dict[str, dict] = {}

RETRIEVAL_K_MIN = 1
RETRIEVAL_K_MAX = 12
APP_VERSION = "1.5.0"


@app.context_processor
def layout_globals():
    return {
        "app_version": APP_VERSION,
        "show_health_pill": True,
        "embed_model": EMBED_MODEL_NAME,
        "default_llm_model": DEFAULT_MODEL,
        "available_models": get_available_models(),
    }


def _store_id() -> str:
    if "store_id" not in session:
        session["store_id"] = str(uuid.uuid4())
    return session["store_id"]


def get_store() -> dict:
    sid = _store_id()
    if sid not in stores:
        stores[sid] = load_store(sid)   # Load from disk on first access
    return stores[sid]


def save_current_store():
    """Save current session data"""
    sid = _store_id()
    if sid in stores:
        save_store(sid, stores[sid])


# ====================== Routes ======================

@app.route("/")
def dashboard():
    return render_template("dashboard.html", active_nav="dashboard")


@app.route("/workspace")
def workspace():
    return render_template("workspace.html", active_nav="workspace")


@app.route("/library")
def library():
    store = get_store()
    chunks = store.get("chunks") or []
    indexed = store.get("index") is not None and bool(chunks)
    doc = store.get("doc_meta")
    avg_chunk_len = sum(len(c) for c in chunks) / len(chunks) if chunks else 0.0
    
    return render_template(
        "library.html",
        active_nav="library",
        indexed=indexed,
        doc=doc,
        avg_chunk_len=avg_chunk_len,
    )


@app.route("/docs")
def docs():
    return render_template("docs.html", active_nav="docs")


@app.route("/settings")
def settings_page():
    return render_template(
        "settings.html",
        active_nav="settings",
        ollama_host=ollama_base_url(),
    )


@app.route("/api/state", methods=["GET"])
def api_state():
    return jsonify(state_payload(get_store()))


@app.route("/api/health", methods=["GET"])
def api_health():
    reachable, err = ollama_server_reachable()
    store = get_store()
    return jsonify({
        "ok": True,
        "ollama_reachable": reachable,
        "ollama_error": err,
        "ollama_host": ollama_base_url(),
        "embed_model": EMBED_MODEL_NAME,
        "llm_model": store.get("selected_model", DEFAULT_MODEL),
    })


@app.route("/api/settings", methods=["POST"])
def api_settings():
    store = get_store()
    data = request.get_json(silent=True) or {}

    try:
        k = int(data.get("retrieval_k", store.get("retrieval_k", 5)))
        k = max(RETRIEVAL_K_MIN, min(RETRIEVAL_K_MAX, k))
        store["retrieval_k"] = k
    except:
        pass

    new_model = data.get("llm_model")
    if new_model:
        store["selected_model"] = new_model

    save_current_store()          # ← Save on settings change
    return jsonify(state_payload(store))


@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file uploaded."}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"ok": False, "error": "Choose a PDF file."}), 400
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"ok": False, "error": "Only PDF files are supported."}), 400

    store = get_store()
    try:
        raw = f.read()
        if not raw:
            return jsonify({"ok": False, "error": "The file is empty."}), 400
        text, page_count = extract_from_pdf_bytes(raw)
        if not text.strip():
            return jsonify({"ok": False, "error": "No extractable text found in this PDF."}), 400

        chunks = chunk_text(text)
        embeddings = embed_chunks(chunks)
        index = create_index(embeddings)

        store["index"] = index
        store["chunks"] = chunks
        store["chat_history"] = []
        store["last_query"] = ""
        store["doc_meta"] = {
            "filename": secure_filename(f.filename) or "document.pdf",
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "chunk_count": len(chunks),
            "page_count": page_count,
            "char_count": len(text),
        }
        
        save_current_store()        # ← Save after upload
        return jsonify(state_payload(store))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/remove-document", methods=["POST"])
def api_remove_document():
    store = get_store()
    store["index"] = None
    store["chunks"] = None
    store["doc_meta"] = None
    store["chat_history"] = []
    store["last_query"] = ""
    save_current_store()
    return jsonify(state_payload(store))


@app.route("/api/clear", methods=["POST"])
def api_clear():
    store = get_store()
    store["chat_history"] = []
    store["last_query"] = ""
    save_current_store()
    return jsonify(state_payload(store))


@app.route("/api/export")
def api_export():
    store = get_store()
    fmt = (request.args.get("format") or "md").lower()
    if fmt not in ("md", "txt"):
        fmt = "md"
    lines: list[str] = []
    meta = store.get("doc_meta") or {}
    if meta.get("filename"):
        lines.append(f"Document: {meta['filename']}")
        lines.append("")
    for m in store["chat_history"]:
        role = m.get("role", "")
        content = m.get("content", "")
        label = "User" if role == "user" else "Assistant"
        lines.append(f"## {label}")
        lines.append("")
        lines.append(content)
        if role == "assistant" and m.get("sources"):
            lines.append("")
            lines.append("Sources:")
            for s in m["sources"]:
                lines.append(f" [{s.get('rank', '')}] {s.get('excerpt', '')}")
        lines.append("")
    body = "\n".join(lines).strip() + "\n"
    if fmt == "txt":
        plain = body.replace("## ", "")
        return Response(plain, mimetype="text/plain; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="docquery-conversation.txt"'})
    return Response(body, mimetype="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="docquery-conversation.md"'})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    store = get_store()
    if store["index"] is None or store["chunks"] is None:
        return jsonify({"ok": False, "error": "Upload a document first."}), 400

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "error": "Enter a question."}), 400

    if message == store["last_query"]:
        return jsonify(state_payload(store))

    store["last_query"] = message
    store["chat_history"].append({"role": "user", "content": message})

    k = store.get("retrieval_k", 5)
    query_embedding = model.encode([message])
    results = search(store["index"], query_embedding, store["chunks"], k=k)
    context = "\n".join([r[0] for r in results])

    selected_model = store.get("selected_model", DEFAULT_MODEL)
    answer = ask_llm(context, message, model=selected_model)

    sources = _sources_from_results(results)
    store["chat_history"].append({"role": "assistant", "content": answer, "sources": sources})
    
    save_current_store()          # ← Save after chat
    return jsonify(state_payload(store))


@app.route("/api/summarize", methods=["POST"])
def api_summarize():
    store = get_store()
    if store["index"] is None or store["chunks"] is None:
        return jsonify({"ok": False, "error": "Upload a document first."}), 400

    k = store.get("retrieval_k", 5)
    query_embedding = model.encode(["summarize document"])
    results = search(store["index"], query_embedding, store["chunks"], k=k)
    context = "\n".join([r[0] for r in results])

    selected_model = store.get("selected_model", DEFAULT_MODEL)
    summary = ask_llm(context, "Summarize in 5 bullet points", model=selected_model)

    sources = _sources_from_results(results)
    store["chat_history"].append({"role": "assistant", "content": summary, "sources": sources})
    
    save_current_store()
    return jsonify(state_payload(store))


@app.route("/api/suggest", methods=["POST"])
def api_suggest():
    store = get_store()
    if store["index"] is None or store["chunks"] is None:
        return jsonify({"ok": False, "error": "Upload a document first."}), 400

    k = min(store.get("retrieval_k", 5), len(store["chunks"]))
    top = store["chunks"][: max(k, 3)]
    context = "\n".join(top)

    selected_model = store.get("selected_model", DEFAULT_MODEL)
    questions = ask_llm(context, "Generate 3 useful questions", model=selected_model)

    sources = [
        {"rank": i + 1, "excerpt": (c.strip()[:320] + "…" if len(c.strip()) > 320 else c.strip())}
        for i, c in enumerate(top)
    ]
    store["chat_history"].append({"role": "assistant", "content": questions, "sources": sources})
    
    save_current_store()
    return jsonify(state_payload(store))


def _sources_from_results(results: list) -> list[dict]:
    sources = []
    for i, (chunk, _dist) in enumerate(results):
        excerpt = chunk.strip()
        if len(excerpt) > 320:
            excerpt = excerpt[:320] + "…"
        sources.append({"rank": i + 1, "excerpt": excerpt})
    return sources


def state_payload(store: dict) -> dict:
    indexed = store["index"] is not None and store["chunks"] is not None
    return {
        "ok": True,
        "indexed": indexed,
        "messages": store["chat_history"],
        "doc": store.get("doc_meta"),
        "retrieval_k": store.get("retrieval_k", 5),
        "llm_model": store.get("selected_model", DEFAULT_MODEL),
        "app_version": APP_VERSION,
        "embed_model": EMBED_MODEL_NAME,
        "available_models": get_available_models(),
    }


if __name__ == "__main__":
    print("🚀 DocQuery Started with Persistence!")
    print(f"Data will be saved in: {os.path.abspath(DATA_DIR)}")
    app.run(debug=True, host="127.0.0.1", port=5000)