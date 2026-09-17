"""
Home.py · IA-SBC
================
Router principal. Acá se hacen, en este orden y una sola vez:
  1. configuración de la página,
  2. login (control de acceso por rol),
  3. hidratación desde Supabase (traer lo que el reboot borró),
  4. registro de las páginas con st.navigation.

Los títulos e íconos de las páginas se definen en CÓDIGO, no en el nombre
del archivo: los emojis en nombres de archivo se rompen al pasar por
GitHub.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from nucleo.config import APP_NOMBRE, APP_SUBTITULO, APP_VERSION  # noqa: E402

st.set_page_config(
    page_title=APP_NOMBRE,
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

from app.estado import exigir_login, es_admin  # noqa: E402
from app.ui import aplicar_estilo  # noqa: E402

aplicar_estilo()
exigir_login()

# Hidratación: el disco de Streamlit Cloud arranca vacío tras un reboot.
# Se hace una vez por sesión y es silenciosa si no hay nube configurada.
from nucleo import nube  # noqa: E402

_resumen = nube.hidratar()
if _resumen["documentos"] or _resumen["estado"]:
    st.toast(f"☁️ Recuperados {_resumen['documentos']} documentos de la nube.")

with st.sidebar:
    st.markdown(f"### 💬 {APP_NOMBRE}")
    st.caption(APP_SUBTITULO)
    st.caption(f"v{APP_VERSION}")
    st.divider()

_conversar = st.Page("paginas/conversacion.py", title="Conversar",
                     icon="💬", default=True)
_documentos = st.Page("paginas/documentos.py", title="Documentos", icon="📚")
_instrucciones = st.Page("paginas/instrucciones.py", title="Instrucciones",
                         icon="🧭")

# El colaborador conversa y ve las fuentes; no carga documentos ni cambia
# las instrucciones (si cualquiera puede reescribir main.md, la app deja
# de responder igual para todos).
_paginas = [_conversar]
if es_admin():
    _paginas += [_documentos, _instrucciones]

st.navigation(_paginas).run()
