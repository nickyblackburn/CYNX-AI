@echo off
cd /d "C:\Users\nickk\Documents\CYNX-AI\moddelfiles"

echo Creating CYN-X model...
ollama create cyn-x -f Modelfile

if errorlevel 1 (
    echo.
    echo ERROR: Ollama model creation failed.
    pause
    exit /b 1
)

cd /d "C:\Users\nickk\Documents\CYNX-AI"

echo.
echo Starting CYN-X web interface...
uvicorn interfaces.web.app:app

pause