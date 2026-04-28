#!/bin/bash

echo "=== Установка моделей Ollama ==="
echo ""

# Определяем имя контейнера
CONTAINER=$(docker ps | grep ollama | awk '{print $1}')

if [ -z "$CONTAINER" ]; then
    echo "❌ Контейнер Ollama не найден!"
    echo "Запустите: docker-compose up -d"
    exit 1
fi

echo "✓ Контейнер Ollama найден: $CONTAINER"
echo ""

# Проверяем текущие модели
echo "1. Текущие установленные модели:"
docker exec $CONTAINER ollama list
echo ""

# Устанавливаем модели
echo "2. Установка моделей..."
echo ""

echo "   Установка qwen2.5:3b (быстрая модель)..."
docker exec $CONTAINER ollama pull qwen2.5:3b
echo ""

echo "   Установка qwen3:8b (средняя модель)..."
docker exec $CONTAINER ollama pull qwen3:8b
echo ""

echo "   Установка llama3.1:8b (лучшая модель)..."
docker exec $CONTAINER ollama pull llama3.1:8b
echo ""

echo "   Проверка nomic-embed-text (для эмбеддингов)..."
docker exec $CONTAINER ollama pull nomic-embed-text
echo ""

# Финальная проверка
echo "3. Финальный список моделей:"
docker exec $CONTAINER ollama list
echo ""

echo "✅ Установка завершена!"
echo ""
echo "Теперь перезапустите backend:"
echo "docker-compose restart backend"
