import os
import uuid
from datetime import datetime, timezone

from flask import Flask, Response, jsonify, render_template, request, session
from werkzeug.utils import secure_filename

from embedding import EMBED_MODEL_NAME, embed_chunks, model
from llm import OLLAMA_MODEL, ask_llm
from ollama_client import ollama_base_url, ollama_server_reachable
from pdf_utils import chunk_text, extract_from_pdf_bytes
from vector_store import create_index, search

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-change-me-in-production")

# Per-session document store (index + chunks do not fit in cookies)
stores: dict[str, dict] = {}

RETRIEVAL_K_MIN = 1
RETRIEVAL_K_MAX = 12
APP_VERSION = "1.3.0"


@app.context_processor
def layout_globals():
    return {
        "app_version": APP_VERSION,
        "show_health_pill": True,
        "embed_model": EMBED_MODEL_NAME,
        "llm_model": OLLAMA_MODEL,
    }


def _store_id() -> str:
    if "store_id" not in session:
        session["store_id"] = str(uuid.uuid4())
    return session["store_id"]


def get_store() -> dict:
    sid = _store_id()
    if sid not in stores:
        stores[sid] = {
            "index": None,
            "chunks": None,
            "chat_history": [],
            "last_query": "",
            "doc_meta": None,
            "retrieval_k": 5,
        }
    else:
        if "retrieval_k" not in stores[sid]:
            stores[sid]["retrieval_k"] = 5
        if "doc_meta" not in stores[sid]:
            stores[sid]["doc_meta"] = None
    return stores[sid]


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
        "app_version": APP_VERSION,
        "embed_model": EMBED_MODEL_NAME,
        "llm_model": OLLAMA_MODEL,
    }


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
    avg_chunk_len = (
        sum(len(c) for c in chunks) / len(chunks) if chunks else 0.0
    )
    dim = None
    if store.get("index") is not None:
        d = getattr(store["index"], "d", None)
        dim = int(d) if d is not None else None
    chunk_sample = ""
    if chunks:
        raw = (chunks[0] or "").strip()
        chunk_sample = raw[:1200] + ("…" if len(raw) > 1200 else "")
    return render_template(
        "library.html",
        active_nav="library",
        indexed=indexed,
        doc=doc,
        avg_chunk_len=avg_chunk_len,
        vector_dim=dim,
        chunk_sample=chunk_sample,
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
    return jsonify(
        {
            "ok": True,
            "ollama_reachable": reachable,
            "ollama_error": err,
            "ollama_host": ollama_base_url(),
            "embed_model": EMBED_MODEL_NAME,
            "llm_model": OLLAMA_MODEL,
        }
    )


@app.route("/api/settings", methods=["POST"])
def api_settings():
    store = get_store()
    data = request.get_json(silent=True) or {}
    try:
        k = int(data.get("retrieval_k", store.get("retrieval_k", 5)))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Invalid retrieval value."}), 400
    k = max(RETRIEVAL_K_MIN, min(RETRIEVAL_K_MAX, k))
    store["retrieval_k"] = k
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
            return jsonify(
                {"ok": False, "error": "No extractable text found in this PDF."}
            ), 400

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
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    return jsonify(state_payload(store))


@app.route("/api/remove-document", methods=["POST"])
def api_remove_document():
    store = get_store()
    store["index"] = None
    store["chunks"] = None
    store["doc_meta"] = None
    store["chat_history"] = []
    store["last_query"] = ""
    return jsonify(state_payload(store))


@app.route("/api/clear", methods=["POST"])
def api_clear():
    store = get_store()
    store["chat_history"] = []
    store["last_query"] = ""
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
                lines.append(f"  [{s.get('rank', '')}] {s.get('excerpt', '')}")
        lines.append("")

    body = "\n".join(lines).strip() + "\n"
    if fmt == "txt":
        plain = body.replace("## ", "")
        return Response(
            plain,
            mimetype="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="docquery-conversation.txt"'
            },
        )

    return Response(
        body,
        mimetype="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="docquery-conversation.md"'
        },
    )


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
    answer = ask_llm(context, message)
    sources = _sources_from_results(results)

    store["chat_history"].append(
        {"role": "assistant", "content": answer, "sources": sources}
    )
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
    summary = ask_llm(context, "Summarize in 5 bullet points")
    sources = _sources_from_results(results)
    store["chat_history"].append(
        {"role": "assistant", "content": summary, "sources": sources}
    )
    return jsonify(state_payload(store))


@app.route("/api/suggest", methods=["POST"])
def api_suggest():
    store = get_store()
    if store["index"] is None or store["chunks"] is None:
        return jsonify({"ok": False, "error": "Upload a document first."}), 400

    k = min(store.get("retrieval_k", 5), len(store["chunks"]))
    top = store["chunks"][: max(k, 3)]
    context = "\n".join(top)
    questions = ask_llm(context, "Generate 3 useful questions")
    sources = [
        {"rank": i + 1, "excerpt": (c.strip()[:320] + "…" if len(c.strip()) > 320 else c.strip())}
        for i, c in enumerate(top)
    ]
    store["chat_history"].append(
        {"role": "assistant", "content": questions, "sources": sources}
    )
    return jsonify(state_payload(store))


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
