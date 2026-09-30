"""
Home.py · IA-SBC
================
El armazón de la app. Acá se decide, en este orden:
  1. configuración de la página,
  2. estilo móvil,
  3. hidratación desde Supabase (traer lo que el reinicio borró),
  4. las secciones y la navegación.

DOS DECISIONES DE NAVEGACIÓN

· **Tres secciones abajo, siempre en una fila.** Esta app se usa de pie,
  con una mano. El menú lateral de Streamlit obliga a tocar la esquina
  superior izquierda, la más lejos del pulgar, así que se oculta.
· **La configuración vive arriba a la derecha**, fuera del camino. Quien
  abre la app viene a conversar, leer o cotizar; administrar es otra
  cosa y no merece un cuarto botón compitiendo con esas tres.
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
    layout="centered",          # en celular, una columna se lee mejor
    initial_sidebar_state="collapsed",
)

from app.estado import es_admin  # noqa: E402
from app.ui import acceso_tope, aplicar_estilo, barra_inferior  # noqa: E402

aplicar_estilo()

# El disco de Streamlit Cloud arranca vacío tras un reinicio. Se hace una
# vez por sesión y es silenciosa si no hay nube configurada.
from nucleo import nube  # noqa: E402

nube.hidratar()

_V = "paginas"
_conversar = st.Page(f"{_V}/conversar.py", title="Conversar",
                     url_path="conversar", default=True)
_biblia = st.Page(f"{_V}/biblia.py", title="Biblia", url_path="biblia")
_personalizar = st.Page(f"{_V}/personalizar.py", title="Personalizar",
                        url_path="personalizar")
_administrar = st.Page(f"{_V}/administrar.py", title="Configuración",
                       url_path="administrar")

_secciones = [_conversar, _biblia, _personalizar]

_navegacion = st.navigation(_secciones + [_administrar], position="hidden")
_en_admin = _navegacion.url_path == _administrar.url_path

acceso_tope(_administrar, es_admin(), _en_admin)
# La barra va SIEMPRE, también dentro de la configuración: es la única
# forma de volver a la app sin buscar un botón de "atrás". Estando en
# configuración no hay ninguna sección marcada como activa.
barra_inferior(_secciones, _navegacion.url_path)
_navegacion.run()
