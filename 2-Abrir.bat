@echo off
REM Abre IA-SBC en el navegador (Windows).
cd /d "%~dp0"
call .venv\Scripts\activate || (echo Falta instalar: corre 1-Instalar.bat & pause & exit /b 1)
streamlit run src/app/Home.py
