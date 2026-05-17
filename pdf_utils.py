import fitz
import re


def clean_text(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"[^\x00-\x7F]+", " ", text)
    text = re.sub(r"[^a-zA-Z0-9.,!?()\n\s-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_from_pdf_bytes(data: bytes) -> tuple[str, int]:
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        page_count = len(doc)
        text = ""
        for page in doc:
            text += page.get_text()
    finally:
        doc.close()
    return clean_text(text), page_count


def extract_text(file):
    data = file.read()
    text, _ = extract_from_pdf_bytes(data)
    return text


def chunk_text(text, chunk_size=300, overlap=50):
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunks.append(text[i : i + chunk_size])
    return chunks
