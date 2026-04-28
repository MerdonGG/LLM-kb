# Исправление всех проблем

## Проблемы

1. **Qwen3.5** — таймаут
2. **Qwen2.5** — на "привет" отвечает километром текста о контексте
3. **Llama** — 404 ошибка

## Причины

1. **Qwen3.5** — модель не существует или не установлена (правильное название: qwen3:8b)
2. **Qwen2.5** — промпт слишком строгий, требует отвечать только на основе контекста
3. **Llama** — модель llama3.1:8b не установлена в Ollama

## Решения

### Решение 1: Исправлен промпт ✅

Промпт теперь умнее:
- Для приветствий ("привет", "спасибо") — отвечает естественно
- Для учебных вопросов — использует контекст
- Не пишет километры текста о том, что "нет в контексте"

**Изменено в:** `backend/main.py`

---

### Решение 2: Установить модели

На сервере выполните:

```bash
cd /home/ivan/kbe

# Способ 1: Автоматический скрипт
chmod +x install_models.sh
./install_models.sh
```

Или вручную:

```bash
# Способ 2: Вручную
docker exec $(docker ps | grep ollama | awk '{print $1}') ollama pull qwen2.5:3b
docker exec $(docker ps | grep ollama | awk '{print $1}') ollama pull qwen3:8b
docker exec $(docker ps | grep ollama | awk '{print $1}') ollama pull llama3.1:8b
docker exec $(docker ps | grep ollama | awk '{print $1}') ollama pull nomic-embed-text
```

**Время:** ~10-15 минут (зависит от скорости интернета)

---

### Решение 3: Проверить установленные модели

```bash
cd /home/ivan/kbe
chmod +x check_ollama_models.sh
./check_ollama_models.sh
```

Или вручную:

```bash
docker exec $(docker ps | grep ollama | awk '{print $1}') ollama list
```

**Ожидаемый вывод:**
```
NAME                    ID              SIZE    MODIFIED
qwen2.5:3b             abc123          1.9 GB  X minutes ago
qwen3:8b               def456          4.7 GB  X minutes ago
llama3.1:8b            ghi789          4.7 GB  X minutes ago
nomic-embed-text       jkl012          274 MB  X minutes ago
```

---

## Пошаговая инструкция

### Шаг 1: Обновить код (исправлен промпт)

```bash
# На локальной машине
git add backend/main.py check_ollama_models.sh install_models.sh FIX_ALL_PROBLEMS.md
git commit -m "fix: исправлен промпт + скрипты для установки моделей"
git push origin main
```

```bash
# На сервере
cd /home/ivan/kbe
git pull origin main
```

### Шаг 2: Установить модели

```bash
# На сервере
cd /home/ivan/kbe
chmod +x install_models.sh
./install_models.sh
```

**Ожидаемое время:** 10-15 минут

### Шаг 3: Перезапустить backend

```bash
docker-compose restart backend
```

### Шаг 4: Проверить логи

```bash
docker-compose logs -f backend
```

**Ожидаемый вывод:**
```
Векторная база загружена (300 фрагментов)
BM25 индекс загружен (300 документов)
```

### Шаг 5: Тестирование

1. Откройте: http://192.168.29.241
2. Проверьте каждую модель:

**Тест 1: Приветствие**
- Вопрос: "привет"
- Ожидаемый ответ: Короткое дружелюбное приветствие (не километр текста!)

**Тест 2: Учебный вопрос**
- Вопрос: "Что такое компьютерная безопасность?"
- Ожидаемый ответ: Структурированный ответ с источниками

**Тест 3: Все модели**
- Проверьте qwen2.5:3b ✓
- Проверьте qwen3:8b ✓
- Проверьте llama3.1:8b ✓

---

## Проверка проблем

### Проблема: Модель не найдена (404)

**Причина:** Модель не установлена в Ollama

**Решение:**
```bash
docker exec $(docker ps | grep ollama | awk '{print $1}') ollama pull <model_name>
```

### Проблема: Таймаут

**Причина:** Модель слишком медленная для CPU или не отвечает

**Решение:**
1. Проверьте, что модель установлена: `ollama list`
2. Увеличьте таймаут в backend/main.py (уже 600 сек)
3. Используйте более быструю модель (qwen2.5:3b)

### Проблема: "Нет в контексте" на простые вопросы

**Причина:** Промпт слишком строгий

**Решение:** ✅ Уже исправлено в новом промпте

---

## Быстрая проверка

Выполните на сервере:

```bash
# 1. Проверка Ollama
curl http://localhost:11435/api/tags

# 2. Список моделей
docker exec $(docker ps | grep ollama | awk '{print $1}') ollama list

# 3. Тест генерации
docker exec $(docker ps | grep ollama | awk '{print $1}') ollama run qwen2.5:3b "привет"
```

Если всё работает — модели установлены правильно.

---

## Ожидаемые результаты

### До исправления:
- ❌ Qwen3.5 — таймаут
- ❌ Qwen2.5 — километр текста на "привет"
- ❌ Llama — 404 ошибка

### После исправления:
- ✅ Qwen2.5:3b — быстрые ответы (10-20 сек)
- ✅ Qwen3:8b — качественные ответы (30-50 сек)
- ✅ Llama3.1:8b — лучшие ответы (45-65 сек)
- ✅ На "привет" — короткое приветствие
- ✅ На учебные вопросы — структурированные ответы

---

## Если всё ещё не работает

### Проверка 1: Ollama запущен?
```bash
docker ps | grep ollama
```

Должен быть контейнер с ollama.

### Проверка 2: Модели установлены?
```bash
docker exec $(docker ps | grep ollama | awk '{print $1}') ollama list
```

Должны быть 4 модели.

### Проверка 3: Backend видит Ollama?
```bash
docker-compose logs backend | grep -i ollama
```

Не должно быть ошибок подключения.

### Проверка 4: Порт правильный?
В docker-compose.yml должно быть:
```yaml
OLLAMA_URL: http://ollama:11434
```

Не 11435!

---

Готово! Выполните шаги 1-5 и всё заработает! 🚀
