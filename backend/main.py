import os
import requests
import chromadb
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.embeddings import Embeddings

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"
LLM_MODEL = "qwen3:8b"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.environ.get("PDF_DIR", os.path.join(BASE_DIR, "pdfs"))
CHROMA_DIR = os.environ.get("CHROMA_DIR", os.path.join(BASE_DIR, "chroma_db"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Кастомный класс эмбеддингов
class OllamaEmbeddingsDirect(Embeddings):
    def embed_documents(self, texts):
        embeddings = []
        for text in texts:
            resp = requests.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": EMBED_MODEL, "input": text},
                timeout=60,
            )
            resp.raise_for_status()
            embeddings.append(resp.json()["embeddings"][0])
        return embeddings

    def embed_query(self, text):
        return self.embed_documents([text])[0]

embedder = OllamaEmbeddingsDirect()
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)

try:
    collection = chroma_client.get_collection("metodichki")
    print(f"Векторная база загружена ({collection.count()} фрагментов)")
except Exception:
    print("Векторная база не найдена. Создаю...")

    PDF_FILES = [
        os.path.join(PDF_DIR, f)
        for f in os.listdir(PDF_DIR)
        if f.lower().endswith(".pdf")
    ]

    docs = []
    for path in PDF_FILES:
        loader = PyMuPDFLoader(path)
        docs.extend(loader.load())

    splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=400)
    chunks = splitter.split_documents(docs)

    try:
        chroma_client.delete_collection("metodichki")
    except Exception:
        pass
    collection = chroma_client.create_collection("metodichki")

    BATCH_SIZE = 50
    texts = [c.page_content for c in chunks]
    ids = [str(i) for i in range(len(chunks))]

    for i in range(0, len(texts), BATCH_SIZE):
        batch_texts = texts[i:i+BATCH_SIZE]
        batch_ids = ids[i:i+BATCH_SIZE]
        batch_embeddings = embedder.embed_documents(batch_texts)
        collection.add(documents=batch_texts, embeddings=batch_embeddings, ids=batch_ids)
        print(f"  Обработано {min(i+BATCH_SIZE, len(texts))}/{len(texts)}")

    print("Векторная база создана!")


def retrieve(question: str, k: int = 8) -> str:
    q_emb = embedder.embed_query(question)
    results = collection.query(query_embeddings=[q_emb], n_results=k)
    return "\n\n".join(results["documents"][0])


PROMPT_TEMPLATE = (
    "Ты помощник курсанта кафедры компьютерной безопасности и экспертизы. "
    "Отвечай только на основе предоставленного контекста из методичек. "
    "Если ответа в контексте нет — так и скажи.\n\n"
    "Контекст:\n{context}\n\n"
    "Вопрос: {question}\n\n"
    "Ответ:"
)


class QuestionRequest(BaseModel):
    question: str


@app.post("/ask")
def ask(req: QuestionRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Вопрос не может быть пустым")

    context = retrieve(req.question)
    prompt = PROMPT_TEMPLATE.format(context=context, question=req.question)

    resp = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    answer = resp.json()["response"]

    return {"answer": answer}


@app.get("/health")
def health():
    return {"status": "ok"}
