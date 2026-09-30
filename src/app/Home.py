"""
Home.py · IA-SBC
================
El armazón de la app. Acá se decide, en este orden:
  1. configuración de la página,
  2. estilo móvil,
  3. hidratación desde Supabase (traer lo que el reinicio borró),
  4. qué secciones existen según quién esté usando la app,
  5. la barra de navegación inferior.

POR QUÉ LA NAVEGACIÓN VA ABAJO Y NO EN EL PANEL LATERAL: esta app se usa
desde el celular, de pie, con una mano. El menú lateral de Streamlit
obliga a tocar una hamburguesa arriba a la izquierda, que es justo la
esquina más lejos del pulgar. Por eso se oculta y se arma una barra
propia abajo, como en cualquier app del teléfono.

El visitante ve tres secciones. El administrador ve una cuarta.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from nucleo.config import APP_NOMBRE  # noqa: E402

st.set_page_config(
    page_title=APP_NOMBRE,
    page_icon="📖",
    layout="centered",          # en celular, una columna se lee mejor
    initial_sidebar_state="collapsed",
)

from app.estado import es_admin  # noqa: E402
from app.ui import aplicar_estilo, barra_inferior  # noqa: E402

aplicar_estilo()

# El disco de Streamlit Cloud arranca vacío tras un reinicio. Se hace una
# vez por sesión y es silenciosa si no hay nube configurada.
from nucleo import nube  # noqa: E402

nube.hidratar()

_V = "paginas"
_conversar = st.Page(f"{_V}/conversar.py", title="Conversar", icon="💬",
                     url_path="conversar", default=True)
_biblia = st.Page(f"{_V}/biblia.py", title="Biblia", icon="📖",
                  url_path="biblia")
_personalizar = st.Page(f"{_V}/personalizar.py", title="Personalizar",
                        icon="✨", url_path="personalizar")
_admin = st.Page(f"{_V}/administrar.py", title="Administrar", icon="⚙️",
                 url_path="administrar")

# El botón de administrar está siempre: es la puerta, no el permiso. Lo
# que hay detrás sí pide clave. Esconderlo obligaría a saberse una URL.
_paginas = [_conversar, _biblia, _personalizar, _admin]

_navegacion = st.navigation(_paginas, position="hidden")
barra_inferior(_paginas, _navegacion.url_path)
_navegacion.run()
