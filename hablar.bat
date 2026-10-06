@echo off
rem Habla con Cyn. Ajustes opcionales (descomenta y cambia):
rem set CYNX_INTERRUPCION=1
rem set CYNX_VOZ=es_ES-davefx-medium
rem set CYNX_SILENCIO_MS=600
cd /d "%~dp0"
.venv\Scripts\python -m cynx_voz
pause
