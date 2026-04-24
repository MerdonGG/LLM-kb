@echo off
echo ========================================
echo  Учебный ассистент КБиЭ
echo ========================================
echo.

:: Запускаем Ollama в фоне
echo [1/3] Запуск Ollama...
start "Ollama" /min ollama serve

timeout /t 3 /nobreak >nul

:: Запускаем FastAPI бэкенд в фоне
echo [2/3] Запуск бэкенда...
start "Backend" /min cmd /c "cd /d C:\llm\backend && uvicorn main:app --host 0.0.0.0 --port 8000"

timeout /t 5 /nobreak >nul

:: Запускаем фронтенд
echo [3/3] Запуск интерфейса...
start "Frontend" /min cmd /c "cd /d C:\llm\frontend && npm run dev"

timeout /t 3 /nobreak >nul

:: Открываем браузер
echo.
echo Открываю браузер...
start http://localhost:5173

echo.
echo ========================================
echo  Всё запущено!
echo  Интерфейс: http://localhost:5173
echo  API:       http://localhost:8000
echo ========================================
echo.
echo Закройте это окно чтобы остановить всё.
pause >nul

:: При закрытии останавливаем все процессы
taskkill /f /fi "WINDOWTITLE eq Ollama*" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq Backend*" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq Frontend*" >nul 2>&1
