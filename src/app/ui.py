"""
app/ui.py
=========
La piel de la app. Desde la v2 el objetivo es que se sienta una app de
celular: menú abajo, una cosa por pantalla, poco texto y nada que
distraiga de lo que se vino a hacer.

CUATRO REGLAS

1. **El pulgar manda.** La navegación va abajo, donde llega el dedo sin
   estirar la mano. Arriba solo queda el título de lo que se está
   mirando.
2. **Funciona en claro y en oscuro.** No se define `[theme]` (forzaría el
   modo claro para todos) y no hay colores de fondo fijos: los acentos
   van con transparencias sobre el fondo del tema.
3. **Un solo lugar audaz.** El acento dorado es el canto de la Biblia —el
   producto real de la planta— y aparece únicamente en la lectura. Todo
   lo demás es azul institucional y silencio.
4. **Esto dibuja, no calcula.**
"""
from __future__ import annotations

import streamlit as st

from nucleo.config import COLOR_ACENTO, COLOR_PRIMARIO
from nucleo.util import recortar

# Alto reservado para la barra inferior: el contenido tiene que poder
# terminar sin quedar tapado por ella.
_ALTO_BARRA = 74

_CSS = f"""
<style>
/* ── Estructura general ─────────────────────────────────── */
.block-container {{
  padding-top: 1.1rem;
  padding-bottom: calc({_ALTO_BARRA}px + env(safe-area-inset-bottom, 0px) + 1rem);
  max-width: 760px;
}}
#MainMenu, footer, header [data-testid="stStatusWidget"] {{ visibility: hidden; }}
h1, h2, h3 {{ letter-spacing: -0.015em; }}

/* El panel lateral no existe para el visitante: toda la navegación está
   abajo. Se muestra solo donde hace falta (administración). */
[data-testid="stSidebar"] {{ display: none; }}

/* ── Encabezado de pantalla ─────────────────────────────── */
.sbc-tope {{ margin: 0 0 1rem 0; }}
.sbc-tope .t {{ font-size: 1.32rem; font-weight: 600; line-height: 1.25; }}
.sbc-tope .s {{ font-size: 0.88rem; opacity: 0.68; margin-top: 0.1rem; }}

/* ── Barra inferior ─────────────────────────────────────── */
.st-key-barra_inferior {{
  position: fixed;
  left: 0; right: 0; bottom: 0;
  z-index: 100;
  background: var(--background-color);
  border-top: 1px solid rgba(128,128,128,0.22);
  padding: 0.35rem 0.4rem calc(0.35rem + env(safe-area-inset-bottom, 0px));
  backdrop-filter: blur(8px);
}}
.st-key-barra_inferior [data-testid="stHorizontalBlock"] {{ gap: 0; }}
.st-key-barra_inferior .stButton > button {{
  width: 100%;
  border: none;
  background: transparent;
  color: inherit;
  opacity: 0.55;
  font-size: 0.72rem;
  font-weight: 500;
  line-height: 1.15;
  padding: 0.35rem 0.1rem 0.25rem;
  white-space: pre-line;
}}
.st-key-barra_inferior .stButton > button:hover {{ background: transparent; opacity: 0.85; }}
.st-key-barra_inferior .stButton > button[kind="primary"] {{
  background: transparent;
  color: {COLOR_PRIMARIO};
  opacity: 1;
}}

/* ── Chat ───────────────────────────────────────────────── */
[data-testid="stChatMessage"] {{
  border-radius: 14px;
  padding: 0.55rem 0.85rem;
  margin-bottom: 0.45rem;
  background: rgba(128,128,128,0.07);
}}
[data-testid="stChatInput"] {{ border-radius: 999px; }}

/* ── Lectura bíblica: el único lugar con el acento dorado ─ */
.sbc-lectura {{
  font-family: Georgia, "Times New Roman", serif;
  font-size: 1.06rem;
  line-height: 1.8;
  border-right: 3px solid #a8842c;
  padding-right: 0.9rem;
}}
.sbc-lectura .v {{
  font-family: inherit;
  font-size: 0.68rem;
  vertical-align: super;
  color: #a8842c;
  margin-right: 0.22rem;
  font-weight: 600;
}}

/* ── Piezas sueltas ─────────────────────────────────────── */
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
    """Encabezado de pantalla: qué estoy mirando y para qué sirve."""
    sub = f'<div class="s">{subtitulo}</div>' if subtitulo else ""
    st.markdown(f'<div class="sbc-tope"><div class="t">{titulo}</div>{sub}</div>',
                unsafe_allow_html=True)


def barra_inferior(paginas: list, actual_url: str) -> None:
    """
    El menú de la app: un botón por sección, fijo abajo.

    Se dibuja con botones de Streamlit dentro de un contenedor con clave,
    y el CSS lo ancla al borde inferior. La sección activa va en color
    institucional; las demás, atenuadas.
    """
    with st.container(key="barra_inferior"):
        columnas = st.columns(len(paginas))
        for col, pagina in zip(columnas, paginas):
            activa = pagina.url_path == actual_url
            etiqueta = f"{pagina.icon}\n{pagina.title}"
            if col.button(etiqueta, key=f"_nav_{pagina.url_path}",
                          type="primary" if activa else "secondary",
                          use_container_width=True) and not activa:
                st.switch_page(pagina)


def chips(etiquetas: list[str], limite: int = 6) -> None:
    """Nombres en etiquetas redondas, con un '+N' si hay más."""
    if not etiquetas:
        return
    html = "".join(f'<span class="sbc-chip">{e}</span>'
                   for e in etiquetas[:limite])
    if len(etiquetas) > limite:
        html += f'<span class="sbc-chip">+{len(etiquetas) - limite}</span>'
    st.markdown(html, unsafe_allow_html=True)


def bloque_fuentes(fuentes: list[dict]) -> None:
    """
    Las fuentes de una respuesta: primero los documentos como etiquetas
    (la pregunta frecuente es "¿de dónde salió esto?") y adentro cada
    pasaje.
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
    """Fila de indicadores. Hasta cuatro: más de eso ya no se leen."""
    pares = pares[:4]
    if not pares:
        return
    for col, (etiqueta, valor) in zip(st.columns(len(pares)), pares):
        col.metric(etiqueta, valor)
