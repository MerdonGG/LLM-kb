import os
import requests
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.embeddings import Embeddings
import chromadb

OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
LLM_MODEL = "qwen3:8b"

# Кастомный класс эмбеддингов через прямой HTTP-запрос
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

# Автоматически берём все PDF из папки, где лежит скрипт
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_FILES = [
    os.path.join(SCRIPT_DIR, f)
    for f in os.listdir(SCRIPT_DIR)
    if f.lower().endswith(".pdf")
]

if not PDF_FILES:
    print("PDF файлы не найдены в папке скрипта!")
    exit(1)

# Загружаем и разбиваем на чанки
print("Загружаю методички...")
for p in PDF_FILES:
    print(f"  - {os.path.basename(p)}")

docs = []
for path in PDF_FILES:
    loader = PyMuPDFLoader(path)
    docs.extend(loader.load())

splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=400)
chunks = splitter.split_documents(docs)
print(f"Разбито на {len(chunks)} фрагментов")

# Создаём векторную базу через chromadb напрямую
print("Создаю векторную базу (это займёт несколько минут)...")
CHROMA_DIR = os.path.join(SCRIPT_DIR, "chroma_db")
embedder = OllamaEmbeddingsDirect()

client = chromadb.PersistentClient(path=CHROMA_DIR)
collection_name = "metodichki"

# Проверяем, существует ли уже коллекция
try:
    collection = client.get_collection(collection_name)
    print(f"Векторная база уже существует ({collection.count} фрагментов)")
except:
    # Удаляем старую коллекцию если есть, чтобы пересоздать
    try:
        client.delete_collection(collection_name)
    except:
        pass
    collection = client.create_collection(collection_name)

    # Добавляем чанки батчами
    BATCH_SIZE = 50
    texts = [c.page_content for c in chunks]
    ids = [str(i) for i in range(len(chunks))]

    for i in range(0, len(texts), BATCH_SIZE):
        batch_texts = texts[i:i+BATCH_SIZE]
        batch_ids = ids[i:i+BATCH_SIZE]
        batch_embeddings = embedder.embed_documents(batch_texts)
        collection.add(documents=batch_texts, embeddings=batch_embeddings, ids=batch_ids)
        print(f"  Обработано {min(i+BATCH_SIZE, len(texts))}/{len(texts)} фрагментов")

    print("Векторная база создана!")

# Функция поиска релевантных фрагментов
def retrieve(question, k=8):
    q_emb = embedder.embed_query(question)
    results = collection.query(query_embeddings=[q_emb], n_results=k)
    docs = results["documents"][0]
    print(f"\n[DEBUG] Найдено фрагментов: {len(docs)}")
    for i, d in enumerate(docs):
        print(f"[DEBUG] Фрагмент {i+1}: {d[:200]}\n")
    return "\n\n".join(docs)

# Промпт
PROMPT_TEMPLATE = (
    "Ты помощник курсанта. Отвечай только на основе предоставленного контекста из методичек. "
    "Если ответа в контексте нет — так и скажи.\n\n"
    "Контекст:\n{context}\n\n"
    "Вопрос: {question}\n\n"
    "Ответ:"
)

def ask(question):
    context = retrieve(question)
    prompt = PROMPT_TEMPLATE.format(context=context, question=question)
    resp = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["response"]

# Диалог с пользователем
print("\nГотово! Задавай вопросы по методичкам (введи 'выход' для завершения)\n")
while True:
    question = input("Вопрос: ").strip()
    if question.lower() in ("выход", "exit", "quit"):
        break
    if not question:
        continue
    answer = ask(question)
    print(f"\nОтвет: {answer}\n")
