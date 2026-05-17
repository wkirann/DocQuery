from sentence_transformers import SentenceTransformer

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

# Load model once
model = SentenceTransformer(EMBED_MODEL_NAME)


def embed_chunks(chunks):
    return model.encode(chunks)
