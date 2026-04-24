#!/bin/bash
echo "Скачиваю модели в Ollama..."

docker exec kbe-ollama ollama pull nomic-embed-text
docker exec kbe-ollama ollama pull qwen3:8b

echo "Готово!"
