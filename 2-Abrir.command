#!/bin/bash
# Abre IA-SBC en el navegador (Mac).
cd "$(dirname "$0")"
source .venv/bin/activate || { echo "Falta instalar: corré 1-Instalar.command"; read -n 1; exit 1; }
streamlit run src/app/Home.py
