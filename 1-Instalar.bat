@echo off
REM Instala el entorno local de IA-SBC (Windows). Doble clic para ejecutar.
cd /d "%~dp0"
echo == IA-SBC . Instalacion ==
py -3 -m venv .venv || python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo Listo. Abri la app con 2-Abrir.bat
pause
