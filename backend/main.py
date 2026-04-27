import os
import requests
import chromadb
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.embeddings import Embeddings
from auth import init_db, register_user, login_user, get_user_by_token, logout_user, log_chat, get_all_users, get_user_chats

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"
LLM_MODEL = "qwen3:8b"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.environ.get("PDF_DIR", os.path.join(BASE_DIR, ".."))
CHROMA_DIR = os.environ.get("CHROMA_DIR", os.path.join(BASE_DIR, "..", "chroma_db"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

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

class RegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str
    group_number: str

class LoginRequest(BaseModel):
    username: str
    password: str

def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Необходима авторизация")
    token = authorization.split(" ")[1]
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Недействительный или истёкший токен")
    return user

def require_admin(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    return user

@app.post("/auth/register")
def register(req: RegisterRequest):
    if not req.username.strip() or not req.password.strip():
        raise HTTPException(status_code=400, detail="Логин и пароль не могут быть пустыми")
    result = register_user(req.username, req.password, req.full_name, req.group_number)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"message": "Регистрация успешна"}

@app.post("/auth/login")
def login(req: LoginRequest):
    result = login_user(req.username, req.password)
    if not result:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    return result

@app.post("/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        logout_user(authorization.split(" ")[1])
    return {"message": "Выход выполнен"}


@app.post("/ask")
def ask(req: QuestionRequest, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
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
    log_chat(user["id"], req.question, answer)
    return {"answer": answer}


@app.get("/admin/users")
def admin_users(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return get_all_users()

@app.get("/admin/users/{user_id}/chats")
def admin_user_chats(user_id: int, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    return get_user_chats(user_id)


@app.get("/health")
def health():
    return {"status": "ok"}
