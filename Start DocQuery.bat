@echo off
title DocQuery - Local RAG Chatbot
echo ========================================
echo     Starting DocQuery...
echo ========================================
echo.

:: Activate virtual environment (if you use one)
call venv\Scripts\activate

echo Checking Ollama...
ollama list >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Ollama is not running!
    echo Please start Ollama first.
    pause
    exit
)

echo Starting DocQuery...
python app.py

pause