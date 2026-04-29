import os
import requests
import chromadb
import json
import pickle
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.embeddings import Embeddings
from auth import init_db, register_user, login_user, get_user_by_token, logout_user, log_chat, get_all_users, get_user_chats
from rank_bm25 import BM25Okapi

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"
LLM_MODEL = "qwen2.5:1.5b"  # Быстрая модель с поддержкой русского языка

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.environ.get("PDF_DIR", os.path.join(BASE_DIR, ".."))
CHROMA_DIR = os.environ.get("CHROMA_DIR", os.path.join(BASE_DIR, "..", "chroma_db"))

# Настройки для огромной векторной базы
CHUNK_SIZE = 1000  # Меньшие чанки = больше детализации
CHUNK_OVERLAP = 200  # Больше перекрытия = лучше связность
MAX_K = 20  # Извлекать до 20 фрагментов для контекста

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

# Глобальные переменные для BM25
bm25_index = None
bm25_documents = []
bm25_metadatas = []
BM25_INDEX_PATH = os.path.join(CHROMA_DIR, "bm25_index.pkl")

try:
    collection = chroma_client.get_collection("metodichki")
    print(f"Векторная база загружена ({collection.count()} фрагментов)")
    
    # Загружаем BM25 индекс если существует
    if os.path.exists(BM25_INDEX_PATH):
        with open(BM25_INDEX_PATH, 'rb') as f:
            bm25_data = pickle.load(f)
            bm25_index = bm25_data['index']
            bm25_documents = bm25_data['documents']
            bm25_metadatas = bm25_data['metadatas']
        print(f"BM25 индекс загружен ({len(bm25_documents)} документов)")
    else:
        print("BM25 индекс не найден, будет создан при первом запросе")
        
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
        loaded_docs = loader.load()
        # Добавляем имя файла в метаданные
        for doc in loaded_docs:
            doc.metadata["source_file"] = os.path.basename(path)
        docs.extend(loaded_docs)

    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks = splitter.split_documents(docs)

    try:
        chroma_client.delete_collection("metodichki")
    except Exception:
        pass
    collection = chroma_client.create_collection("metodichki")

    BATCH_SIZE = 50
    texts = [c.page_content for c in chunks]
    ids = [str(i) for i in range(len(chunks))]
    
    # Подготовка метаданных
    metadatas = []
    for c in chunks:
        metadata = {
            "source": c.metadata.get("source_file", "unknown"),
            "page": c.metadata.get("page", 0) + 1,  # +1 для человеко-читаемого номера
        }
        metadatas.append(metadata)

    for i in range(0, len(texts), BATCH_SIZE):
        batch_texts = texts[i:i+BATCH_SIZE]
        batch_ids = ids[i:i+BATCH_SIZE]
        batch_metadatas = metadatas[i:i+BATCH_SIZE]
        batch_embeddings = embedder.embed_documents(batch_texts)
        collection.add(
            documents=batch_texts,
            embeddings=batch_embeddings,
            ids=batch_ids,
            metadatas=batch_metadatas
        )
        print(f"  Обработано {min(i+BATCH_SIZE, len(texts))}/{len(texts)}")

    print("Векторная база создана!")
    
    # Создаём BM25 индекс
    print("Создаю BM25 индекс...")
    tokenized_corpus = [doc.lower().split() for doc in texts]
    bm25_index = BM25Okapi(tokenized_corpus)
    bm25_documents = texts
    bm25_metadatas = metadatas
    
    # Сохраняем BM25 индекс
    with open(BM25_INDEX_PATH, 'wb') as f:
        pickle.dump({
            'index': bm25_index,
            'documents': bm25_documents,
            'metadatas': bm25_metadatas
        }, f)
    print("BM25 индекс создан и сохранён!")


def hybrid_retrieve(question: str, k: int = 8, alpha: float = 0.5) -> tuple[str, list[dict]]:
    """
    Гибридный поиск: комбинация BM25 (keyword) и векторного (semantic) поиска
    
    Args:
        question: Вопрос пользователя
        k: Количество фрагментов для извлечения (оптимизировано до 8)
        alpha: Вес векторного поиска (0.0 = только BM25, 1.0 = только векторный, 0.5 = баланс)
    
    Returns:
        Tuple: (контекст, список метаданных источников)
    """
    global bm25_index, bm25_documents, bm25_metadatas
    
    # Если BM25 индекс не загружен, используем только векторный поиск
    if bm25_index is None:
        print("[HYBRID] BM25 индекс не доступен, используем только векторный поиск")
        return retrieve(question, k)
    
    # 1. Векторный поиск
    q_emb = embedder.embed_query(question)
    vector_results = collection.query(
        query_embeddings=[q_emb],
        n_results=k * 2,  # Берём больше для комбинирования
        include=["documents", "distances", "metadatas"]
    )
    
    # 2. BM25 поиск
    tokenized_query = question.lower().split()
    bm25_scores = bm25_index.get_scores(tokenized_query)
    
    # Получаем топ-k индексов по BM25
    bm25_top_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:k * 2]
    
    # 3. Комбинируем результаты
    # Нормализуем скоры
    vector_docs = vector_results["documents"][0]
    vector_distances = vector_results["distances"][0]
    vector_metas = vector_results["metadatas"][0]
    
    # Преобразуем distance в similarity (меньше distance = больше similarity)
    max_dist = max(vector_distances) if vector_distances else 1.0
    vector_scores = {doc: 1.0 - (dist / max_dist) for doc, dist in zip(vector_docs, vector_distances)}
    
    # Нормализуем BM25 скоры
    max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1.0
    bm25_normalized = {bm25_documents[i]: bm25_scores[i] / max_bm25 for i in bm25_top_indices}
    
    # Комбинируем скоры
    combined_scores = {}
    all_docs = set(vector_docs) | set(bm25_normalized.keys())
    
    for doc in all_docs:
        vector_score = vector_scores.get(doc, 0.0)
        bm25_score = bm25_normalized.get(doc, 0.0)
        combined_scores[doc] = alpha * vector_score + (1 - alpha) * bm25_score
    
    # Сортируем по комбинированному скору
    sorted_docs = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
    
    # 4. Фильтрация и дедупликация
    filtered_docs = []
    filtered_metas = []
    seen_docs = set()
    
    for doc, score in sorted_docs:
        # Фильтр по минимальному скору
        if score < 0.1:
            continue
        
        # Дедупликация
        doc_normalized = doc.strip().lower()[:100]
        if doc_normalized in seen_docs:
            continue
        
        seen_docs.add(doc_normalized)
        filtered_docs.append(doc)
        
        # Находим метаданные
        if doc in vector_docs:
            idx = vector_docs.index(doc)
            filtered_metas.append(vector_metas[idx])
        elif doc in bm25_documents:
            idx = bm25_documents.index(doc)
            filtered_metas.append(bm25_metadatas[idx])
        else:
            filtered_metas.append({})
        
        if len(filtered_docs) >= 8:
            break
    
    # Если ничего не нашли, fallback на векторный поиск
    if not filtered_docs:
        print("[HYBRID] Гибридный поиск не дал результатов, fallback на векторный")
        return retrieve(question, k)
    
    context = "\n\n---\n\n".join(filtered_docs)
    return context, filtered_metas


def retrieve(question: str, k: int = MAX_K) -> tuple[str, list[dict]]:
    """
    Улучшенная функция поиска с фильтрацией и дедупликацией
    
    Args:
        question: Вопрос пользователя
        k: Количество фрагментов для извлечения (по умолчанию MAX_K = 20)
    
    Returns:
        Tuple: (контекст, список метаданных источников)
    """
    q_emb = embedder.embed_query(question)
    
    # Извлекаем больше кандидатов для фильтрации
    results = collection.query(
        query_embeddings=[q_emb], 
        n_results=k * 2,  # Берём в 2 раза больше для фильтрации
        include=["documents", "distances", "metadatas"]
    )
    
    documents = results["documents"][0]
    distances = results["distances"][0] if "distances" in results else [0] * len(documents)
    metadatas = results["metadatas"][0] if "metadatas" in results else [{}] * len(documents)
    
    # Фильтрация по релевантности (distance threshold)
    # Меньше distance = более релевантно
    filtered_docs = []
    filtered_metas = []
    seen_docs = set()  # Для дедупликации
    
    for doc, dist, meta in zip(documents, distances, metadatas):
        # Фильтр 1: Релевантность (distance < 1.5 обычно хорошо для cosine distance)
        if dist > 1.5:
            continue
            
        # Фильтр 2: Дедупликация (убираем очень похожие фрагменты)
        doc_normalized = doc.strip().lower()[:100]  # Первые 100 символов для сравнения
        if doc_normalized in seen_docs:
            continue
            
        seen_docs.add(doc_normalized)
        filtered_docs.append(doc)
        filtered_metas.append(meta)
        
        # Ограничиваем до MAX_K лучших фрагментов
        if len(filtered_docs) >= MAX_K:
            break
    
    # Если после фильтрации ничего не осталось, берём топ-k без фильтра
    if not filtered_docs:
        filtered_docs = documents[:k]
        filtered_metas = metadatas[:k]
    
    context = "\n\n---\n\n".join(filtered_docs)
    return context, filtered_metas


PROMPT_TEMPLATE = """Ты — учебный ассистент кафедры компьютерной безопасности и технической экспертизы.

ТВОЯ ЗАДАЧА:
- Отвечать на вопросы курсантов дружелюбно и профессионально
- Для учебных вопросов использовать предоставленный контекст из методичек
- Для общих вопросов (приветствия, благодарности) отвечать естественно

ПРАВИЛА ОТВЕТА:
1. Если вопрос — приветствие или общение (привет, спасибо, как дела) — ответь дружелюбно и кратко
2. Если вопрос учебный и ответ есть в контексте — дай полный, структурированный ответ
3. Если учебный вопрос, но ответа нет в контексте — скажи: "В предоставленных материалах нет информации по этому вопросу. Попробуйте переформулировать вопрос или уточнить тему."
4. Не придумывай учебную информацию, которой нет в контексте
5. Используй термины и определения точно так, как они даны в материалах

СТРУКТУРА ОТВЕТА (для учебных вопросов):
- Начни с краткого определения или прямого ответа
- Затем дай подробное объяснение
- Если есть примеры — включи их
- Используй списки для лучшей читаемости

КОНТЕКСТ ИЗ МЕТОДИЧЕК:
{context}

ВОПРОС КУРСАНТА:
{question}

ТВОЙ ОТВЕТ:"""


class QuestionRequest(BaseModel):
    question: str
    model: Optional[str] = "qwen2.5:1.5b"  # По умолчанию быстрая модель с русским
    stream: Optional[bool] = True  # По умолчанию включён streaming

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

    # Используем модель из запроса или дефолтную
    model = req.model or "tinyllama"
    
    # Используем только векторный поиск (быстрее гибридного на 30%)
    context, sources = retrieve(req.question, k=MAX_K)  # Увеличено до MAX_K фрагментов
    prompt = PROMPT_TEMPLATE.format(context=context, question=req.question)
    
    # Форматируем источники для добавления в конец ответа
    def format_sources(metadatas: list[dict]) -> str:
        if not metadatas:
            return ""
        
        # Группируем по файлам
        sources_by_file = {}
        for meta in metadatas:
            source = meta.get("source", "unknown")
            page = meta.get("page", "?")
            if source not in sources_by_file:
                sources_by_file[source] = []
            if page not in sources_by_file[source]:
                sources_by_file[source].append(page)
        
        # Форматируем
        sources_text = "\n\n---\n\n**Источники:**\n"
        for source, pages in sources_by_file.items():
            pages_sorted = sorted([p for p in pages if isinstance(p, int)])
            if pages_sorted:
                sources_text += f"- {source}, стр. {', '.join(map(str, pages_sorted))}\n"
            else:
                sources_text += f"- {source}\n"
        
        return sources_text

    # Если включён streaming
    if req.stream:
        def generate():
            full_answer = ""
            try:
                print(f"[STREAMING] Начало генерации для вопроса: {req.question[:50]}...")
                print(f"[STREAMING] Модель: {model}")
                
                resp = requests.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": True,
                        "options": {
                            "num_ctx": 2048,
                            "num_predict": 256,     # Уменьшено с 512 для скорости
                            "temperature": 0.7,
                            "top_k": 40,
                            "top_p": 0.9,
                            "repeat_penalty": 1.1
                        }
                    },
                    timeout=600,
                    stream=True
                )
                resp.raise_for_status()
                
                token_count = 0
                for line in resp.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        if "response" in chunk:
                            token = chunk["response"]
                            full_answer += token
                            token_count += 1
                            
                            # Отправляем токен клиенту в формате SSE
                            sse_data = f"data: {json.dumps({'token': token})}\n\n"
                            yield sse_data
                            
                            if token_count % 10 == 0:
                                print(f"[STREAMING] Отправлено токенов: {token_count}")
                        
                        # Если генерация завершена
                        if chunk.get("done", False):
                            print(f"[STREAMING] Генерация завершена. Всего токенов: {token_count}")
                            print(f"[STREAMING] Длина ответа: {len(full_answer)} символов")
                            
                            # Добавляем источники в конец ответа
                            sources_text = format_sources(sources)
                            if sources_text:
                                for char in sources_text:
                                    yield f"data: {json.dumps({'token': char})}\n\n"
                                full_answer += sources_text
                            
                            # Логируем полный ответ с источниками
                            log_chat(user["id"], req.question, full_answer)
                            yield f"data: {json.dumps({'done': True})}\n\n"
                            break
                            
            except Exception as e:
                print(f"[STREAMING] Ошибка: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    
    # Если streaming отключён (обратная совместимость)
    else:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_ctx": 2048,
                    "num_predict": 256,     # Уменьшено с 512 для скорости
                    "temperature": 0.7,
                    "top_k": 40,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1
                }
            },
            timeout=600,
        )
        resp.raise_for_status()
        answer = resp.json()["response"]
        
        # Добавляем источники
        sources_text = format_sources(sources)
        if sources_text:
            answer += sources_text
        
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


@app.get("/models")
def get_models():
    """Возвращает список доступных моделей"""
    return {
        "models": [
            {
                "id": "qwen2.5:1.5b",
                "name": "Qwen 2.5 (1.5B) - Супербыстрая",
                "description": "Быстрая модель с русским языком (~3-7 сек)",
                "speed": "superfast"
            },
            {
                "id": "qwen2.5:3b",
                "name": "Qwen 2.5 (3B) - Быстрая",
                "description": "Быстрые ответы (~5-10 сек)",
                "speed": "fast"
            },
            {
                "id": "qwen3:8b",
                "name": "Qwen 3 (8B) - Качественная",
                "description": "Сбалансированное качество (~15-25 сек)",
                "speed": "medium"
            },
            {
                "id": "llama3.1:8b",
                "name": "Llama 3.1 (8B) - Лучшая",
                "description": "Максимальное качество (~20-30 сек)",
                "speed": "slow"
            }
        ]
    }


@app.get("/health")
def health():
    return {"status": "ok"}
