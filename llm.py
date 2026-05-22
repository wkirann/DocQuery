# llm.py
import ollama
import requests

DEFAULT_MODEL = "llama3.1:8b"   # Best one you have

def get_available_models():
    """Reliable way to get all local Ollama models"""
    models = set()

    # Method 1: Using ollama library
    try:
        response = ollama.list()
        for model in response.get('models', []):
            models.add(model['name'])
    except:
        pass

    # Method 2: Direct HTTP call (more reliable)
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=8)
        if r.status_code == 200:
            data = r.json()
            for model in data.get('models', []):
                models.add(model['name'])
    except:
        pass

    # Final fallback
    if not models:
        models = {"llama3:latest", "llama3.1:8b"}

    return sorted(list(models))


def ask_llm(context: str, question: str, model: str = None):
    if model is None:
        model = DEFAULT_MODEL

    prompt = f"""You are a helpful, accurate assistant.
Use ONLY the provided context to answer the question.
If the answer is not in the context, say: "I don't know based on the document."

Context:
{context}

Question: {question}

Answer:"""

    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        return response['message']['content'].strip()
    except Exception as e:
        return f"Error with model '{model}': {str(e)}"