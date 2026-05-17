import shutil
import subprocess

OLLAMA_MODEL = "llama3"


def ask_llm(context, question):
    prompt = f"""
You are a helpful assistant.

Use ONLY the provided context to answer the question.
If the answer is not in the context, say:
"I don't know based on the document."

Give a clear and concise answer.

Context:
{context}

Question:
{question}
"""

    if not shutil.which("ollama"):
        return (
            "Ollama is not available on this system PATH. "
            "Install Ollama from https://ollama.com and try again."
        )

    try:
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=prompt.encode(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        return "The model stopped responding in time. Try a shorter question or check Ollama."
    except OSError as e:
        return f"Could not run Ollama: {e}"

    out = result.stdout.decode(errors="replace").strip()
    if result.returncode != 0:
        err = result.stderr.decode(errors="replace").strip()
        hint = f" {err}" if err else ""
        return f"The model returned an error (code {result.returncode}).{hint}"

    return out or "(Empty response from model.)"
