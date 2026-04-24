# 📄 DocQuery – Local RAG Document Assistant

DocQuery is a fully local Retrieval-Augmented Generation (RAG) system that allows users to interact with PDF documents using natural language.

---

## 🚀 Features

* 📄 Upload and query PDF documents
* 🧠 Context-aware answers using local LLM
* 📚 Source transparency with retrieved chunks
* 📊 Document summarization
* ❓ Suggested questions generation
* 🔒 Fully local (no paid APIs)

---

## 🛠️ Tech Stack

* Streamlit (UI)
* FAISS (Vector Database)
* Sentence Transformers (Embeddings)
* Ollama (Local LLM)

---

## ⚙️ How It Works

1. Extract text from PDF
2. Split into chunks
3. Generate embeddings
4. Store in FAISS
5. Retrieve relevant chunks
6. Generate answer using LLM

---

## ▶️ Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## 📌 Future Improvements

* Multi-document support
* Persistent vector storage
* Advanced retrieval methods

---

## 👨‍💻 Author

Kiran Wagh
