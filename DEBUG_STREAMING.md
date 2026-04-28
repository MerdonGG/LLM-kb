# Отладка Streaming

## Проблема
Индикатор загрузки (три точки) показывается, но текст не появляется.

## Шаги отладки

### 1. Проверка на тестовой HTML странице

Откройте в браузере: `http://192.168.29.241/test_streaming.html`

1. Нажмите "Войти" (логин/пароль уже заполнены)
2. Нажмите "Спросить"
3. Смотрите на логи внизу страницы

**Что должно произойти:**
- Появится сообщение "✓ Авторизация успешна"
- Появится сообщение "✓ Соединение установлено"
- Начнут появляться сообщения "Получено токенов: 10, 20, 30..."
- Текст должен появляться в верхнем блоке

**Если не работает:**
- Смотрите на ошибки в логах
- Откройте DevTools (F12) → Console
- Откройте DevTools (F12) → Network → найдите запрос к `/ask`

### 2. Проверка логов backend

На сервере выполните:
```bash
docker-compose logs -f backend
```

**Что должно быть в логах:**
```
[STREAMING] Начало генерации для вопроса: Что такое компьютерная безопасность?...
[STREAMING] Модель: qwen2.5:3b
[STREAMING] Отправлено токенов: 10
[STREAMING] Отправлено токенов: 20
...
[STREAMING] Генерация завершена. Всего токенов: 150
[STREAMING] Длина ответа: 850 символов
```

### 3. Проверка с помощью Python скрипта

На локальной машине:
```bash
python test_streaming.py
```

**Что должно произойти:**
- Авторизация
- Отправка вопроса
- Получение токенов в реальном времени
- Вывод полного ответа

### 4. Проверка с помощью curl

```bash
# Получить токен
TOKEN=$(curl -s -X POST http://192.168.29.241/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"516129@32aA"}' \
  | jq -r '.token')

echo "Token: $TOKEN"

# Отправить вопрос со streaming
curl -N -X POST http://192.168.29.241/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "question": "Что такое компьютерная безопасность?",
    "model": "qwen2.5:3b",
    "stream": true
  }'
```

**Что должно произойти:**
- Токены должны появляться в реальном времени
- Формат: `data: {"token":"текст"}`

### 5. Проверка DevTools в основном приложении

1. Откройте http://192.168.29.241
2. Войдите в систему
3. Откройте DevTools (F12)
4. Перейдите на вкладку Network
5. Задайте вопрос
6. Найдите запрос к `/ask`
7. Посмотрите на Response

**Что проверить:**
- Status Code должен быть 200
- Content-Type должен быть `text/event-stream`
- В Response должны быть строки вида `data: {"token":"..."}`

### 6. Проверка Console в DevTools

Откройте Console и посмотрите на ошибки:
- Ошибки парсинга JSON
- Ошибки сети
- Любые другие ошибки

## Возможные проблемы и решения

### Проблема 1: Content-Type не `text/event-stream`
**Решение:** Проверьте nginx.conf, возможно он переписывает заголовки

### Проблема 2: Токены не приходят
**Решение:** Проверьте логи backend, возможно Ollama не отвечает

### Проблема 3: Ошибки парсинга JSON
**Решение:** Проверьте формат данных в Network → Response

### Проблема 4: CORS ошибки
**Решение:** Проверьте настройки CORS в backend/main.py

### Проблема 5: Nginx буферизует ответ
**Решение:** Добавьте в nginx.conf:
```nginx
proxy_buffering off;
proxy_cache off;
proxy_set_header Connection '';
proxy_http_version 1.1;
chunked_transfer_encoding off;
```

## Быстрая проверка

Выполните все команды по порядку:

```bash
# 1. Проверка здоровья backend
curl http://192.168.29.241/health

# 2. Проверка моделей
curl http://192.168.29.241/models

# 3. Проверка логов
ssh ivan@192.168.29.241 "cd /home/ivan/kbe && docker-compose logs --tail=50 backend"

# 4. Проверка Ollama
ssh ivan@192.168.29.241 "curl http://localhost:11435/api/tags"
```

## Если ничего не помогает

1. Откатите изменения:
```bash
cd /home/ivan/kbe
git log --oneline -5
git reset --hard <commit_before_streaming>
docker-compose down
docker-compose up -d --build
```

2. Попробуйте без streaming:
В `frontend/src/App.jsx` измените:
```javascript
body: JSON.stringify({ question, model: selectedModel, stream: false }),
```
