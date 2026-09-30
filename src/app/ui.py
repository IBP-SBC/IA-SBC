"""
app/ui.py
=========
La piel de la app. El objetivo es que se sienta una app de celular: menú
abajo, una cosa por pantalla, poco texto y nada que distraiga.

CUATRO REGLAS

1. **El pulgar manda.** La navegación va abajo, donde llega el dedo sin
   estirar la mano. El acceso de configuración va arriba a la derecha,
   fuera del camino de quien solo viene a usar la app.
2. **Sin iconos.** Los nombres se leen; los símbolos hay que
   interpretarlos. Y una fila de emojis de colores delata que la pantalla
   la armó una máquina. Texto y silencio.
3. **Funciona en claro y en oscuro.** No se define `[theme]` (forzaría el
   modo claro para todos) y no hay colores de fondo fijos. El único
   acento fuerte es el dorado del canto, y solo en la lectura.
4. **Esto dibuja, no calcula.**
"""
from __future__ import annotations

import streamlit as st

from nucleo.config import COLOR_ACENTO, COLOR_PRIMARIO
from nucleo.util import recortar

# Alto reservado para la barra inferior: el contenido tiene que poder
# terminar sin quedar tapado por ella.
_ALTO_BARRA = 62

_CSS = f"""
<style>
/* ---- Estructura general ---- */
.block-container {{
  padding-top: 2.6rem;
  padding-bottom: calc({_ALTO_BARRA}px + env(safe-area-inset-bottom, 0px) + 1.2rem);
  max-width: 760px;
}}
#MainMenu, footer, header [data-testid="stStatusWidget"] {{ visibility: hidden; }}
[data-testid="stSidebar"] {{ display: none; }}
h1, h2, h3 {{ letter-spacing: -0.015em; }}

/* ---- Encabezado de pantalla ---- */
.sbc-tope {{ margin: 0 0 1rem 0; }}
.sbc-tope .t {{ font-size: 1.3rem; font-weight: 600; line-height: 1.25; }}
.sbc-tope .s {{ font-size: 0.87rem; opacity: 0.65; margin-top: 0.1rem; }}

/* ---- Acceso de configuracion, arriba a la derecha ---- */
.st-key-acceso_tope {{
  position: fixed;
  top: calc(0.5rem + env(safe-area-inset-top, 0px));
  right: 0.8rem;
  z-index: 101;
  width: auto;
}}
.st-key-acceso_tope .stButton > button {{
  border: none;
  background: transparent;
  color: inherit;
  opacity: 0.55;
  font-size: 0.78rem;
  font-weight: 500;
  padding: 0.2rem 0.4rem;
  min-height: 0;
}}
.st-key-acceso_tope .stButton > button:hover {{ opacity: 1; }}

/* ---- Barra inferior ---- */
.st-key-barra_inferior {{
  position: fixed;
  left: 0; right: 0; bottom: 0;
  z-index: 100;
  background: var(--background-color);
  border-top: 1px solid rgba(128,128,128,0.22);
  padding: 0.3rem 0.3rem calc(0.3rem + env(safe-area-inset-bottom, 0px));
}}

/* EL ARREGLO QUE IMPORTA: Streamlit apila las columnas una debajo de
   otra cuando la pantalla es angosta, que es justo el caso del celular.
   Una barra de navegacion en vertical ocupa media pantalla y deja de ser
   una barra. Aca se le fuerza la fila y se reparte el ancho en partes
   iguales, pase lo que pase con el ancho del telefono. */
.st-key-barra_inferior [data-testid="stHorizontalBlock"] {{
  flex-direction: row !important;
  flex-wrap: nowrap !important;
  gap: 0 !important;
  align-items: stretch;
}}
.st-key-barra_inferior [data-testid="stColumn"] {{
  flex: 1 1 0 !important;
  width: auto !important;
  min-width: 0 !important;
}}
.st-key-barra_inferior .stButton > button {{
  width: 100%;
  border: none;
  background: transparent;
  color: inherit;
  opacity: 0.5;
  font-size: 0.8rem;
  font-weight: 500;
  padding: 0.5rem 0.1rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.st-key-barra_inferior .stButton > button:hover {{
  background: transparent;
  opacity: 0.8;
}}
.st-key-barra_inferior .stButton > button[kind="primary"] {{
  background: transparent;
  color: {COLOR_PRIMARIO};
  opacity: 1;
  box-shadow: inset 0 2px 0 0 {COLOR_PRIMARIO};
}}

/* ---- Chat ---- */
[data-testid="stChatMessage"] {{
  border-radius: 14px;
  padding: 0.55rem 0.85rem;
  margin-bottom: 0.45rem;
  background: rgba(128,128,128,0.07);
}}

/* ---- Lectura biblica: el unico lugar con el acento dorado ---- */
.sbc-lectura {{
  font-family: Georgia, "Times New Roman", serif;
  font-size: 1.06rem;
  line-height: 1.8;
  border-right: 3px solid #a8842c;
  padding-right: 0.9rem;
}}
.sbc-lectura .v {{
  font-size: 0.68rem;
  vertical-align: super;
  color: #a8842c;
  margin-right: 0.22rem;
  font-weight: 600;
}}

/* ---- Piezas sueltas ---- */
.sbc-chip {{
  display: inline-block;
  padding: 0.12rem 0.55rem;
  margin: 0.12rem 0.25rem 0.12rem 0;
  border: 1px solid {COLOR_ACENTO}55;
  background: {COLOR_ACENTO}14;
  border-radius: 999px;
  font-size: 0.76rem;
}}
.sbc-fuente {{
  border-left: 3px solid {COLOR_ACENTO}66;
  padding: 0.12rem 0 0.12rem 0.7rem;
  margin: 0.4rem 0;
  font-size: 0.85rem;
}}
.sbc-fuente span {{ opacity: 0.7; }}
.stButton > button[kind="primary"] {{
  background-color: {COLOR_PRIMARIO};
  border-color: {COLOR_PRIMARIO};
  border-radius: 12px;
}}
</style>
"""


def aplicar_estilo() -> None:
    """Inyecta el CSS. Se llama una vez, desde Home.py."""
    st.markdown(_CSS, unsafe_allow_html=True)


def tope(titulo: str, subtitulo: str = "") -> None:
    """Encabezado de pantalla: que estoy mirando y para que sirve."""
    sub = f'<div class="s">{subtitulo}</div>' if subtitulo else ""
    st.markdown(f'<div class="sbc-tope"><div class="t">{titulo}</div>{sub}</div>',
                unsafe_allow_html=True)


def acceso_tope(pagina_admin, hay_sesion: bool, en_admin: bool) -> None:
    """
    El acceso de configuracion, arriba a la derecha y discreto.

    Esta siempre visible porque es la puerta, no el permiso: esconderlo
    obligaria a saberse una direccion de memoria. Pero no compite con las
    tres secciones de abajo, que son lo que la gente vino a usar.
    """
    if en_admin:
        return
    with st.container(key="acceso_tope"):
        etiqueta = "Configuración" if hay_sesion else "Entrar"
        if st.button(etiqueta, key="_acceso_admin"):
            st.switch_page(pagina_admin)


def barra_inferior(paginas: list, actual_url: str) -> None:
    """
    El menu: un boton por seccion, fijo abajo y SIEMPRE en una fila.

    Solo el nombre, sin icono. Con tres secciones y nombres cortos el
    texto se lee de un vistazo y no hay que descifrar un simbolo.
    """
    with st.container(key="barra_inferior"):
        columnas = st.columns(len(paginas))
        for col, pagina in zip(columnas, paginas):
            activa = pagina.url_path == actual_url
            if col.button(pagina.title, key=f"_nav_{pagina.url_path}",
                          type="primary" if activa else "secondary",
                          use_container_width=True) and not activa:
                st.switch_page(pagina)


def chips(etiquetas: list[str], limite: int = 6) -> None:
    """Nombres en etiquetas redondas, con un '+N' si hay mas."""
    if not etiquetas:
        return
    html = "".join(f'<span class="sbc-chip">{e}</span>'
                   for e in etiquetas[:limite])
    if len(etiquetas) > limite:
        html += f'<span class="sbc-chip">+{len(etiquetas) - limite}</span>'
    st.markdown(html, unsafe_allow_html=True)


def bloque_fuentes(fuentes: list[dict]) -> None:
    """
    Las fuentes de una respuesta: primero los documentos (la pregunta
    frecuente es "de donde salio esto") y adentro cada pasaje.
    """
    if not fuentes:
        return
    documentos = []
    for f in fuentes:
        doc = f["etiqueta"].split(" · ")[0]
        if doc not in documentos:
            documentos.append(doc)
    with st.expander(f"De dónde salió ({len(documentos)})"):
        chips(documentos)
        st.markdown("")
        for f in fuentes:
            st.markdown(
                f'<div class="sbc-fuente"><b>{f["etiqueta"]}</b><br>'
                f'<span>{recortar(f["extracto"], 200)}</span></div>',
                unsafe_allow_html=True)


def metricas(pares: list[tuple[str, str]]) -> None:
    """Fila de indicadores. Hasta cuatro: mas de eso ya no se leen."""
    pares = pares[:4]
    if not pares:
        return
    for col, (etiqueta, valor) in zip(st.columns(len(pares)), pares):
        col.metric(etiqueta, valor)
