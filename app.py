import streamlit as st
from pdf_utils import extract_text, chunk_text
from embedding import embed_chunks, model
from vector_store import create_index, search
from llm import ask_llm

# -------------------------------
# PAGE CONFIG
# -------------------------------
st.set_page_config(
    page_title="DocQuery",
    page_icon="📄",
    layout="wide"
)

# -------------------------------
# SESSION STATE
# -------------------------------
if "index" not in st.session_state:
    st.session_state.index = None
    st.session_state.chunks = None
    st.session_state.chat_history = []
    st.session_state.summary = None
    st.session_state.suggested_questions = None

# -------------------------------
# HEADER (CLEAN)
# -------------------------------
st.markdown("## 📄 DocQuery")
st.caption("Local AI-powered document assistant")

st.markdown("---")

# -------------------------------
# SIDEBAR
# -------------------------------
with st.sidebar:
    st.header("Upload Document")

    uploaded_file = st.file_uploader("Upload PDF", type="pdf")

    if uploaded_file and st.session_state.index is None:
        with st.spinner("Processing document..."):
            text = extract_text(uploaded_file)
            chunks = chunk_text(text)

            embeddings = embed_chunks(chunks)
            index = create_index(embeddings)

            st.session_state.index = index
            st.session_state.chunks = chunks
            st.session_state.chat_history = []
            st.session_state.summary = None
            st.session_state.suggested_questions = None

        st.success("Document ready!")

    st.markdown("---")

    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history = []

# -------------------------------
# HOME PAGE
# -------------------------------
if st.session_state.index is None:

    st.markdown("### Understand Your Documents with AI")

    st.markdown("""
**DocQuery** lets you interact with your PDFs using local AI.

### ✨ What you can do:
- Ask questions from documents  
- Get accurate answers with context  
- View sources used for answers  
- Generate summaries instantly  

---

👉 Upload a PDF from the sidebar to begin.
""")

# -------------------------------
# CHAT PAGE
# -------------------------------
else:

    # Action buttons
    col1, col2 = st.columns(2)

    with col1:
        if st.button("📄 Summarize"):
            with st.spinner("Generating summary..."):
                context = "\n".join(st.session_state.chunks[:10])
                st.session_state.summary = ask_llm(context, "Summarize this document")

    with col2:
        if st.button("❓ Suggested Questions"):
            with st.spinner("Generating..."):
                context = "\n".join(st.session_state.chunks[:10])
                st.session_state.suggested_questions = ask_llm(
                    context,
                    "Generate 3 useful questions from this document"
                )

    # Summary
    if st.session_state.summary:
        with st.expander("📄 Summary"):
            st.write(st.session_state.summary)

    # Suggested questions
    if st.session_state.suggested_questions:
        with st.expander("❓ Suggested Questions"):
            st.write(st.session_state.suggested_questions)

    st.markdown("---")

    # Chat history
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.write(chat["content"])

    # Input
    query = st.chat_input("Ask something about your document...")

    if query:

        st.session_state.chat_history.append({"role": "user", "content": query})

        with st.chat_message("user"):
            st.write(query)

        with st.spinner("Thinking..."):

            query_embedding = model.encode([query])

            results = search(
                st.session_state.index,
                query_embedding,
                st.session_state.chunks
            )

            context = "\n".join([r[0] for r in results])

            answer = ask_llm(context, query)

        with st.chat_message("assistant"):
            st.write(answer)

            st.caption("Answer based on these sections:")

            # Sources
            with st.expander("📚 Sources Used"):
                for i, (chunk, score) in enumerate(results):
                    st.write(f"**Chunk {i+1} (Score: {score:.2f})**")
                    st.write(chunk[:250] + "...")

            # Explain answer
            if st.button("🧠 Explain Answer"):
                explanation_prompt = f"""
Explain how this answer was generated using the context.

Context:
{context}

Answer:
{answer}
"""
                explanation = ask_llm(context, explanation_prompt)

                st.write("### 🧠 Explanation")
                st.write(explanation)

        st.session_state.chat_history.append({
            "role": "assistant",
            "content": answer
        })