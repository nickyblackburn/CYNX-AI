@echo off
rem Instala todo lo necesario para CYN-X Voz. Se puede volver a ejecutar sin problema.
cd /d "%~dp0"

where ollama >nul 2>nul || winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements
py -V:3.12 --version >nul 2>nul || py install 3.12

if not exist .venv py -V:3.12 -m venv .venv
.venv\Scripts\python -m pip install -U pip
.venv\Scripts\python -m pip install -r requirements-voz.txt || goto error

ollama pull qwen3.5:9b || goto error
ollama pull qwen3-embedding:0.6b || goto error
.venv\Scripts\python -m piper.download_voices es_MX-claude-high --data-dir cynx_voz\datos\voces || goto error

echo.
echo Listo. Ejecuta hablar.bat para empezar.
pause
exit /b 0

:error
echo.
echo ERROR: algo fallo arriba.
pause
exit /b 1
