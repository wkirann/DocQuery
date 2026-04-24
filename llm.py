import subprocess

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

    result = subprocess.run(
        ["ollama", "run", "llama3"],
        input=prompt.encode(),
        stdout=subprocess.PIPE
    )

    return result.stdout.decode()