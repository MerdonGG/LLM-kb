@echo off
REM Скрипт для обновления backend с TinyLlama и огромной векторной базой

echo 🔄 Обновление backend с TinyLlama...
echo.

REM Останавливаем backend контейнер
echo ⏹️  Останавливаем backend...
docker-compose stop backend

REM Пересобираем backend
echo 🔨 Пересобираем backend...
docker-compose build backend

REM Запускаем backend
echo ▶️  Запускаем backend...
docker-compose up -d backend

REM Проверяем статус
echo ✅ Проверяем статус...
docker-compose ps backend

echo.
echo ✨ Готово! Backend обновлён с TinyLlama:
echo    - Модель: TinyLlama (самая маленькая)
echo    - Размер чанков: 1000 символов (было 2000)
echo    - Перекрытие: 200 символов (было 400)
echo    - Макс. фрагментов: 20 (было 4)
echo.
echo 📊 Ожидаемое ускорение: +50-70% за счёт:
echo    - Меньшей модели (TinyLlama)
echo    - Больше контекста из PDF (20 фрагментов)
echo    - Меньших чанков = больше детализации
echo.
echo ⚠️  При первом запуске векторная база будет пересоздана
echo ⚠️  Это может занять несколько минут
echo.
pause
