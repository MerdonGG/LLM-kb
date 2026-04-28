#!/usr/bin/env python3
"""
Тестовый скрипт для проверки streaming API
"""
import requests
import json

# Настройки
BASE_URL = "http://192.168.29.241"  # Или http://localhost если локально
USERNAME = "admin"
PASSWORD = "516129@32aA"

print("=== Тест streaming API ===\n")

# 1. Логин
print("1. Авторизация...")
login_resp = requests.post(
    f"{BASE_URL}/auth/login",
    json={"username": USERNAME, "password": PASSWORD}
)

if login_resp.status_code != 200:
    print(f"Ошибка авторизации: {login_resp.status_code}")
    print(login_resp.text)
    exit(1)

token = login_resp.json()["token"]
print(f"✓ Токен получен: {token[:20]}...\n")

# 2. Тест streaming запроса
print("2. Отправка вопроса с streaming...")
question = "Что такое компьютерная безопасность?"

resp = requests.post(
    f"{BASE_URL}/ask",
    json={
        "question": question,
        "model": "qwen2.5:3b",
        "stream": True
    },
    headers={"Authorization": f"Bearer {token}"},
    stream=True
)

if resp.status_code != 200:
    print(f"Ошибка запроса: {resp.status_code}")
    print(resp.text)
    exit(1)

print(f"✓ Статус: {resp.status_code}")
print(f"✓ Content-Type: {resp.headers.get('content-type')}")
print("\n3. Получение токенов:\n")

full_text = ""
token_count = 0

try:
    for line in resp.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            print(f"[RAW] {line_str}")
            
            if line_str.startswith('data: '):
                try:
                    data = json.loads(line_str[6:])
                    
                    if 'token' in data:
                        token_count += 1
                        full_text += data['token']
                        print(f"[TOKEN #{token_count}] {data['token']}", end='', flush=True)
                    
                    if 'done' in data and data['done']:
                        print("\n\n✓ Генерация завершена")
                        break
                    
                    if 'error' in data:
                        print(f"\n✗ Ошибка: {data['error']}")
                        break
                        
                except json.JSONDecodeError as e:
                    print(f"\n✗ Ошибка парсинга JSON: {e}")
                    print(f"   Строка: {line_str}")

except KeyboardInterrupt:
    print("\n\n✗ Прервано пользователем")

print(f"\n\n4. Итого:")
print(f"   Получено токенов: {token_count}")
print(f"   Длина текста: {len(full_text)} символов")
print(f"\n5. Полный ответ:")
print("=" * 60)
print(full_text)
print("=" * 60)
