#!/bin/bash

echo "=== Проверка установленных моделей Ollama ==="
echo ""

# Проверка доступности Ollama
echo "1. Проверка доступности Ollama..."
curl -s http://localhost:11435/api/tags || echo "Ollama недоступен!"
echo ""

# Список установленных моделей
echo "2. Список установленных моделей:"
docker exec kbe-ollama-1 ollama list
echo ""

# Проверка конкретных моделей
echo "3. Проверка наличия моделей:"
echo "   - qwen2.5:3b"
docker exec kbe-ollama-1 ollama show qwen2.5:3b 2>&1 | head -5
echo ""

echo "   - qwen3:8b"
docker exec kbe-ollama-1 ollama show qwen3:8b 2>&1 | head -5
echo ""

echo "   - llama3.1:8b"
docker exec kbe-ollama-1 ollama show llama3.1:8b 2>&1 | head -5
echo ""

echo "=== Рекомендации ==="
echo "Если модели нет, установите:"
echo "docker exec kbe-ollama-1 ollama pull qwen2.5:3b"
echo "docker exec kbe-ollama-1 ollama pull qwen3:8b"
echo "docker exec kbe-ollama-1 ollama pull llama3.1:8b"
