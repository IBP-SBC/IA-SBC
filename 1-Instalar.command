#!/bin/bash
# Instala el entorno local de IA-SBC (Mac). Doble clic para ejecutar.
cd "$(dirname "$0")"
echo "== IA-SBC · Instalación =="
python3 -m venv .venv || { echo "No se encontró python3. Instalá Python 3.11+"; read -n 1; exit 1; }
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo ""
echo "Listo. Abrí la app con 2-Abrir.command"
read -n 1 -s -r -p "Presioná cualquier tecla para cerrar..."
