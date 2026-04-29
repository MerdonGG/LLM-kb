# Настройка Groq API

## Что нужно сделать на сервере:

### 1. Подключитесь к серверу по SSH:
```bash
ssh ivan@192.168.29.241
```

### 2. Перейдите в папку проекта:
```bash
cd /home/ivan/kbe
```

### 3. Обновите код из GitHub:
```bash
git pull
```

### 4. Создайте файл .env с Groq API ключом:
```bash
echo "GROQ_API_KEY=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" > .env
```

### 5. Запустите скрипт обновления:
```bash
chmod +x update_backend_groq.sh
./update_backend_groq.sh
```

### 6. После запуска скрипта дождитесь, пока он покажет логи backend, затем нажмите `Ctrl+C` чтобы выйти из логов

---

## Доступные модели:

| Модель | Скорость | Описание |
|--------|----------|----------|
| `groq-llama-3.3-70b-versatile` | ~1-2 сек | Самая быстрая |
| `groq-llama-3.1-8b-instant` | ~2-3 сек | Быстрая |
| `groq-gemma-7b-it` | ~3-5 сек | Баланс |
| `qwen2.5:3b` | ~5-10 сек | Локальная |
| `qwen3:8b` | ~15-25 сек | Локальная |
| `llama3.1:8b` | ~20-30 сек | Локальная |

---

## Как использовать:

**В интерфейсе** выберите модель из dropdown. Модели с префиксом `groq-` будут использовать Groq API.

**Пример запроса:**
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"question": "Привет", "model": "groq-llama-3.3-70b-versatile", "stream": true}'
```

---

## Важно:

- Groq API ключ хранится в файле `.env` на сервере (не в git)
- Модели с префиксом `groq-` используют Groq API
- Локальные модели без префикса используют Ollama
